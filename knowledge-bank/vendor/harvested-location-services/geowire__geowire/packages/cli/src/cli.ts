import { createInterface } from "node:readline/promises";
import { resolve } from "node:path";
import type { Logger } from "@geowirehq/provider-sdk";
import type { Strategy, LatLng, TravelMode } from "@geowirehq/schema";
import { createGeoFromEnv } from "@geowirehq/server";
import { consoleIO, type IO } from "./io.js";
import { loadDotEnv } from "./env.js";
import { parseFlags, parseNear, flagInt } from "./args.js";
import { runSearch } from "./commands/search.js";
import { runReverse } from "./commands/reverse.js";
import { runRoute } from "./commands/route.js";
import { runGet } from "./commands/get.js";
import { runTest } from "./commands/test.js";
import { runServe } from "./commands/serve.js";
import { runInit } from "./commands/init.js";

const logger: Logger = {
  debug: () => {},
  info: (m, ...a) => process.stderr.write(`[geowire:info] ${m} ${a.join(" ")}\n`.trimEnd() + "\n"),
  warn: (m, ...a) => process.stderr.write(`[geowire:warn] ${m} ${a.join(" ")}\n`.trimEnd() + "\n"),
  error: (m, ...a) => process.stderr.write(`[geowire:error] ${m} ${a.join(" ")}\n`.trimEnd() + "\n"),
};

function apiKeysFromEnv(): string[] | undefined {
  return process.env.GEOWIRE_API_KEYS?.split(",").map((s) => s.trim()).filter(Boolean);
}

const HELP = `geowire — geo data gateway CLI

Usage:
  geowire                          Start the REST + MCP server (zero-config)
  geowire serve [--config f]       Start the server with a config file
                [--port n] [--host h]
  geowire search <query>           One-shot search in the terminal
                [--near lat,lon] [--radius m] [--limit n]
                [--country CC] [--strategy first-success|merge] [--json]
  geowire reverse <lat,lon>        Reverse-geocode a coordinate → nearest place
                [--json]
  geowire route <lat,lon> <lat,lon> [...]   Directions between waypoints (no key)
                [--mode driving|walking|cycling] [--geometry] [--json]
  geowire get <provider:id>        Fetch one place by provider reference
                [--json]           (needs a getPlace-capable provider, e.g.
                                    Google: geowire get google:ChIJN1t_tDeuEmsR...)
  geowire test                     Check configured provider connections
  geowire init                     Interactive setup wizard (.env + config)
  geowire help | version

Env:
  GOOGLE_MAPS_API_KEY  enable Google provider (BYOK)
  GEOWIRE_INTERNAL_CSV path to your own places CSV
  GEOWIRE_CONFIG       path to geowire.config.yaml
  GEOWIRE_API_KEYS     comma-separated Bearer keys for the server`;

async function serveCmd(rest: string[], io: IO): Promise<number> {
  const { flags } = parseFlags(rest);
  if (typeof flags.config === "string") process.env.GEOWIRE_CONFIG = flags.config;
  const geo = createGeoFromEnv(logger);
  const port = flagInt(flags.port) ?? flagInt(process.env.PORT) ?? 4980;
  const host = typeof flags.host === "string" ? flags.host : (process.env.HOST ?? "0.0.0.0");
  return runServe({ geo, port, host, apiKeys: apiKeysFromEnv() }, io);
}

async function searchCmd(rest: string[], io: IO): Promise<number> {
  const { _, flags } = parseFlags(rest);
  const query = _.join(" ").trim();
  if (!query) {
    io.err('usage: geowire search <query>   e.g. geowire search "coffee near Gangnam"');
    return 1;
  }
  const near = typeof flags.near === "string" ? parseNear(flags.near) : undefined;
  const geo = createGeoFromEnv(logger);
  return runSearch(
    geo,
    {
      query,
      near,
      radiusMeters: flagInt(flags.radius),
      limit: flagInt(flags.limit),
      country: typeof flags.country === "string" ? flags.country : undefined,
      strategy: typeof flags.strategy === "string" ? (flags.strategy as Strategy) : undefined,
      json: flags.json === true,
    },
    io,
  );
}

async function reverseCmd(rest: string[], io: IO): Promise<number> {
  const { _, flags } = parseFlags(rest);
  const location = parseNear(_.join(""));
  if (!location) {
    io.err('usage: geowire reverse <lat,lon>   e.g. geowire reverse 37.5665,126.9780');
    return 1;
  }
  const geo = createGeoFromEnv(logger);
  return runReverse(geo, { location, json: flags.json === true }, io);
}

async function routeCmd(rest: string[], io: IO): Promise<number> {
  const { _, flags } = parseFlags(rest);
  const waypoints = _.map((s) => parseNear(s)).filter((p): p is LatLng => p != null);
  if (waypoints.length < 2) {
    io.err('usage: geowire route <lat,lon> <lat,lon> [...]   e.g. geowire route 37.5665,126.9780 37.4979,127.0276');
    return 1;
  }
  const mode =
    typeof flags.mode === "string" ? (flags.mode as TravelMode) : undefined;
  const geo = createGeoFromEnv(logger);
  return runRoute(geo, { waypoints, mode, geometry: flags.geometry === true, json: flags.json === true }, io);
}

async function getCmd(rest: string[], io: IO): Promise<number> {
  const { _, flags } = parseFlags(rest);
  const id = _[0]?.trim();
  if (!id) {
    io.err('usage: geowire get <provider:id>   e.g. geowire get nominatim:node/240109189');
    return 1;
  }
  const geo = createGeoFromEnv(logger);
  return runGet(geo, { id, json: flags.json === true }, io);
}

async function initCmd(io: IO): Promise<number> {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  try {
    return await runInit({ ask: (q) => rl.question(q), cwd: process.cwd(), io });
  } finally {
    rl.close();
  }
}

/** argv(명령 이후 부분)로 CLI를 실행하고 종료 코드를 반환한다 */
export async function run(argv: string[], io: IO = consoleIO): Promise<number> {
  loadDotEnv(resolve(process.cwd(), ".env"));
  const [cmd, ...rest] = argv;
  switch (cmd) {
    case undefined:
    case "serve":
      return serveCmd(rest, io);
    case "search":
      return searchCmd(rest, io);
    case "reverse":
      return reverseCmd(rest, io);
    case "route":
      return routeCmd(rest, io);
    case "get":
      return getCmd(rest, io);
    case "test":
      return runTest(createGeoFromEnv(logger), io);
    case "init":
      return initCmd(io);
    case "help":
    case "--help":
    case "-h":
      io.out(HELP);
      return 0;
    case "version":
    case "--version":
    case "-v":
      io.out("geowire 0.1.2");
      return 0;
    default:
      io.err(`Unknown command: ${cmd}\n`);
      io.out(HELP);
      return 1;
  }
}

/** serve/기본(서버 기동)은 listen이 프로세스를 유지하므로 exit하지 않는다 */
export function keepsProcessAlive(argv: string[]): boolean {
  const [cmd] = argv;
  return cmd === undefined || cmd === "serve";
}
