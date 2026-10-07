#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { DeliveryClient } from "./client.js";
import { ConfigError, DEFAULT_EXPRESS_BASE, DEFAULT_PLATFORM_BASE, loadConfig } from "./config.js";
import { instrumentToolCalls, Telemetry } from "./telemetry.js";
import type { DeliveryConfig } from "./types.js";
import { registerExpressTools } from "./tools/express.js";
import { registerPlatformTools } from "./tools/platform.js";
import { registerRawTool } from "./tools/raw.js";

/**
 * Prose handed to the calling model in the `initialize` result — the only place
 * it learns what the tool list cannot say: which API this is, where the money
 * and the point of no return are, and which failures lie about their cause.
 */
const INSTRUCTIONS =
  "Это B2B API Яндекс Доставки: отправления корпоративного клиента с договором и токеном из " +
  "кабинета dostavka.yandex.ru, а не сервис для частных отправителей; хост экспресса " +
  "b2b.taxi.yandex.net — это Доставка, а не API Такси. Контура два и они независимы: экспресс (день " +
  "в день, заявки) и платформа (доставка в другой день, ПВЗ и постаматы) — разные хосты, иногда " +
  "токены разных кабинетов, разные единицы: у экспресса деньги строкой-decimal и метры/кг, у " +
  "платформы копейки целым числом и см/граммы. Лимиты Яндекса не опубликованы: 429 повторяется " +
  "автоматически с учётом Retry-After, 5xx и обрывы связи — только для расчётов, чтений и создания " +
  "заявки, поэтому после сбоя записи не повторяйте её, а перечитайте состояние. Если 401/403 идут " +
  "по всему контуру, а второй работает, это токен другого кабинета или смена пароля в ЛК, а не " +
  "нехватка прав. Расчёты ничего не бронируют, но реальную доставку заказывают " +
  "express_accept_claim, platform_confirm_offer и express_create_claim с auto_accept=true, а отмена " +
  "бывает платной; тестовая среда есть только у платформы — у экспресса безопасны лишь расчёт и " +
  "чтение.";

/** The per-contour token drop-offs, in the historical check order (missing_token wins). */
type MissingReason = "missing_token" | "missing_express_token" | "missing_platform_token";

/**
 * Which token is missing, in the same order the old startup checks died in —
 * the telemetry dashboard groups by these codes, so the order is pinned:
 * with no tokens at all it stays missing_token, never a contour-specific code.
 */
function missingTokenReason(config: DeliveryConfig): MissingReason | undefined {
  if (!config.expressToken && !config.platformToken) return "missing_token";
  if (!config.expressToken) return "missing_express_token";
  if (!config.platformToken) return "missing_platform_token";
  return undefined;
}

/**
 * Prepended to INSTRUCTIONS when a token is missing. The model reads this
 * before it picks a tool, so an unconfigured session opens with the fix rather
 * than with a failed call. There is no in-chat login here: the token comes only
 * from the environment, so the fix is the operator's — set the variables in the
 * MCP client's server config and restart the server. Per contour on purpose: a
 * half-configured server keeps serving the contour it has a token for, and the
 * prefix must not talk the model out of using it.
 */
function unconfiguredPrefix(reason: MissingReason): string {
  const restart = "в конфигурации MCP-клиента и перезапустить сервер — переменные читаются только при старте. ";
  switch (reason) {
    case "missing_token":
      return (
        "ВНИМАНИЕ: Яндекс Доставка ещё не подключена — токен не задан, поэтому любой вызов " +
        "инструмента вернёт ошибку. Оператор должен задать YANDEX_DELIVERY_TOKEN (Bearer-токен из " +
        "кабинета dostavka.yandex.ru → «Интеграции» → «Получить токен»; если Экспресс и Платформа " +
        "подключены в разных кабинетах — YANDEX_DELIVERY_EXPRESS_TOKEN и YANDEX_DELIVERY_PLATFORM_TOKEN) " +
        restart
      );
    case "missing_express_token":
      return (
        "ВНИМАНИЕ: у экспресс-контура нет токена — инструменты express_* и raw_request с " +
        "contour=express вернут ошибку; платформенный контур настроен и работает. Оператор должен " +
        "задать YANDEX_DELIVERY_TOKEN (общий) или YANDEX_DELIVERY_EXPRESS_TOKEN (токен из кабинета " +
        "dostavka.yandex.ru → «Интеграции» → «Получить токен») " +
        restart
      );
    case "missing_platform_token":
      return (
        "ВНИМАНИЕ: у платформенного контура нет токена — инструменты platform_* и raw_request с " +
        "contour=platform вернут ошибку; экспресс-контур настроен и работает. Оператор должен " +
        "задать YANDEX_DELIVERY_TOKEN (общий) или YANDEX_DELIVERY_PLATFORM_TOKEN (токен из кабинета " +
        "dostavka.yandex.ru → «Интеграции» → «Получить токен») " +
        restart
      );
  }
}

/** Reads the package version so the server reports its real version to MCP clients. */
function readVersion(): string {
  try {
    const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
    return typeof pkg.version === "string" ? pkg.version : "0.0.0";
  } catch {
    return "0.0.0";
  }
}

/**
 * Loads the config without dying on a bad value. A server that exits here never
 * completes the MCP handshake, so the user sees a red cross and no reason —
 * instead the problem is carried into the session, where the model can read it
 * and relay it. (Missing tokens are not an error at all — loadConfig leaves the
 * fields undefined; today it has no malformed-value checks either, so the catch
 * guards future ones.)
 */
function loadConfigOrDegraded(telemetry: Telemetry): {
  config: DeliveryConfig;
  problem?: ConfigError;
} {
  try {
    return { config: loadConfig() };
  } catch (err) {
    if (!(err instanceof ConfigError)) throw err;
    console.error(`Error: ${err.message}`);
    // Fire-and-forget now that the process survives: the historical
    // `startup_failed` funnel stays comparable, but nothing blocks startup.
    telemetry.send("startup_failed", { reason: err.reason });
    return {
      config: {
        expressBase: process.env.YANDEX_DELIVERY_EXPRESS_BASE_URL || DEFAULT_EXPRESS_BASE,
        platformBase: process.env.YANDEX_DELIVERY_PLATFORM_BASE_URL || DEFAULT_PLATFORM_BASE,
        lang: process.env.YANDEX_DELIVERY_LANG || "ru",
      },
      problem: err,
    };
  }
}

async function main(): Promise<void> {
  // Anonymous usage pings (ids/names/versions only, never data or arguments);
  // opt out with ASKADS_TELEMETRY=0. Built before the config so a config
  // problem can be reported; wired to the server before tools register.
  const telemetry = new Telemetry(readVersion());
  const { config, problem } = loadConfigOrDegraded(telemetry);
  const client = new DeliveryClient(config);

  // Decided once, at startup: tokens come only from the environment, so an
  // unconfigured start stays unconfigured until the operator sets the
  // variables and restarts the server.
  const missing = missingTokenReason(config);

  const server = new McpServer(
    {
      name: "mcp-yandex-dostavka",
      version: readVersion(),
    },
    // Surfaces as `instructions` in the initialize result.
    {
      instructions:
        missing === undefined
          ? INSTRUCTIONS
          : unconfiguredPrefix(missing) +
            (problem ? `Проблема конфигурации: ${problem.message} ` : "") +
            INSTRUCTIONS,
    },
  );

  instrumentToolCalls(server, telemetry);
  server.server.oninitialized = () => {
    telemetry.setClientInfo(server.server.getClientVersion());
    // Split on purpose: `server_start` keeps meaning "a usable install
    // started", so the unconfigured case gets its own event instead of
    // inflating that number. The reason vocabulary is the historical closed
    // set, in the old check order.
    if (missing === undefined) telemetry.send("server_start");
    else telemetry.send("unconfigured_start", { reason: problem?.reason ?? missing });
  };

  registerExpressTools(server, client);
  registerPlatformTools(server, client);
  registerRawTool(server, client);

  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error(
    `mcp-yandex-dostavka running on stdio${
      missing === undefined ? "" : " (no token — set the environment variables and restart)"
    }`,
  );
}

main().catch((err) => {
  console.error("Fatal error starting mcp-yandex-dostavka:", err);
  process.exit(1);
});
