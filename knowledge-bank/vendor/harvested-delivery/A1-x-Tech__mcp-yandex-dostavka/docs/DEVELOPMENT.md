# Development

## Requirements

- Node.js 20+ (the published package ships compiled `dist/`; `npx` needs no separate
  install). CI runs the suite on Node 20, 22 and 24.

## Commands

```bash
npm install
npm run dev        # run from source with tsx watch
npm test           # unit tests + dist smoke (node:test), no network
npm run typecheck  # type-check src + tests (no emit)
npm run build      # clean dist/ and compile with tsc
npm run smoke      # live READ-ONLY call: claims/search with limit 1
```

## Local run

```bash
npm run build
YANDEX_DELIVERY_TOKEN=... node dist/index.js
# optional: YANDEX_DELIVERY_EXPRESS_TOKEN / YANDEX_DELIVERY_PLATFORM_TOKEN,
#           YANDEX_DELIVERY_EXPRESS_BASE_URL / YANDEX_DELIVERY_PLATFORM_BASE_URL,
#           YANDEX_DELIVERY_LANG, YANDEX_DELIVERY_TIMEOUT_MS, YANDEX_DELIVERY_MAX_RETRIES
```

`npm run smoke` needs the same credentials and makes one live read on the express
contour (no writes). Remember this is a **write API** overall: the unit suite never
touches the network, but manual testing with a real token can create real claims —
prefer `express_check_price`/`express_search_claims` when poking around, and note
that only the platform contour has a test environment
(`YANDEX_DELIVERY_PLATFORM_BASE_URL=https://b2b.taxi.tst.yandex.net`).

## Tests

Unit tests mock `globalThis.fetch` (client) or use a fake server + mock/real client
(tools), so the whole suite runs offline. Put a `*.test.ts` next to the code it
covers; `npm run typecheck && npm test` is the gate (also run by `prepublishOnly`).
`test/dist-smoke.test.js` additionally exercises the built `dist/` artifact,
including a real MCP handshake over stdio.

## Телеметрия использования

Сервер отправляет анонимные события на `usage.gistrec.cloud` (`server_start`
при подключении клиента к настроенной установке, `unconfigured_start` с кодом
причины при старте без токена, `tool_call` с **именем** инструмента и
`startup_failed` с кодом причины при невалидной конфигурации), чтобы считать
активные установки и востребованность тулов.
В событии только обезличенные технические поля: случайный идентификатор установки
(`~/.config/mcp-yandex-dostavka/instance-id`), версия пакета, имя и версия
AI-приложения из MCP-handshake, версия Node.js и ОС.

Токен, данные аккаунта, аргументы вызовов и тексты запросов не отправляются
и не сохраняются (реализация — `src/telemetry.ts`). Отправка идёт в фоне
с таймаутом 2 с и молча пропускается при любой ошибке. Отключение для всех
MCP-серверов Ask Ads разом: `ASKADS_TELEMETRY=0`.
