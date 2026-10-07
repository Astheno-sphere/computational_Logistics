import { test } from "node:test";
import assert from "node:assert/strict";

import { loadConfig } from "./config.js";

/** Every env var the config reads — cleared by default in each test. */
const ALL_VARS: Record<string, string | undefined> = {
  YANDEX_DELIVERY_TOKEN: undefined,
  YANDEX_DELIVERY_EXPRESS_TOKEN: undefined,
  YANDEX_DELIVERY_PLATFORM_TOKEN: undefined,
  YANDEX_DELIVERY_EXPRESS_BASE_URL: undefined,
  YANDEX_DELIVERY_PLATFORM_BASE_URL: undefined,
  YANDEX_DELIVERY_LANG: undefined,
  YANDEX_DELIVERY_TIMEOUT_MS: undefined,
  YANDEX_DELIVERY_MAX_RETRIES: undefined,
};

function withEnv(vars: Record<string, string | undefined>, run: () => void): void {
  const merged = { ...ALL_VARS, ...vars };
  const saved = new Map(Object.keys(merged).map((k) => [k, process.env[k]]));
  for (const [k, v] of Object.entries(merged)) {
    if (v === undefined) delete process.env[k];
    else process.env[k] = v;
  }
  try {
    run();
  } finally {
    for (const [k, v] of saved) {
      if (v === undefined) delete process.env[k];
      else process.env[k] = v;
    }
  }
}

/**
 * Missing tokens used to throw here, which killed the process before the MCP
 * handshake and left the user with a silent red cross. It is now a survivable
 * state: the server starts, answers initialize/tools/list, and the client
 * raises CredentialsError per contour at call time (pinned in client.test.ts).
 * Pinned here because reverting it would restore that dead end.
 */
test("no tokens at all is not an error — the config loads with empty fields", () => {
  withEnv({}, () => {
    const config = loadConfig();
    assert.equal(config.expressToken, undefined);
    assert.equal(config.platformToken, undefined);
    assert.equal(config.expressBase, "https://b2b.taxi.yandex.net");
    assert.equal(config.platformBase, "https://b2b-authproxy.taxi.yandex.net");
  });
});

test("only an express token leaves the platform contour bare, without throwing", () => {
  withEnv({ YANDEX_DELIVERY_EXPRESS_TOKEN: "exp" }, () => {
    const config = loadConfig();
    assert.equal(config.expressToken, "exp");
    assert.equal(config.platformToken, undefined);
  });
});

test("only a platform token leaves the express contour bare, without throwing", () => {
  withEnv({ YANDEX_DELIVERY_PLATFORM_TOKEN: "plt" }, () => {
    const config = loadConfig();
    assert.equal(config.expressToken, undefined);
    assert.equal(config.platformToken, "plt");
  });
});

test("an empty value is treated as absent, not as an empty credential", () => {
  withEnv(
    {
      YANDEX_DELIVERY_TOKEN: "",
      YANDEX_DELIVERY_EXPRESS_TOKEN: "",
      YANDEX_DELIVERY_PLATFORM_TOKEN: "",
    },
    () => {
      const config = loadConfig();
      assert.equal(config.expressToken, undefined);
      assert.equal(config.platformToken, undefined);
    },
  );
});

test("the shared token fills both contours and defaults apply", () => {
  withEnv({ YANDEX_DELIVERY_TOKEN: "shared" }, () => {
    const config = loadConfig();
    assert.equal(config.expressToken, "shared");
    assert.equal(config.platformToken, "shared");
    assert.equal(config.expressBase, "https://b2b.taxi.yandex.net");
    assert.equal(config.platformBase, "https://b2b-authproxy.taxi.yandex.net");
    assert.equal(config.lang, "ru");
    assert.equal(config.timeoutMs, 60_000);
    assert.equal(config.maxRetries, 3);
  });
});

test("per-contour tokens override the shared one", () => {
  withEnv(
    {
      YANDEX_DELIVERY_TOKEN: "shared",
      YANDEX_DELIVERY_EXPRESS_TOKEN: "exp",
      YANDEX_DELIVERY_PLATFORM_TOKEN: "plt",
    },
    () => {
      const config = loadConfig();
      assert.equal(config.expressToken, "exp");
      assert.equal(config.platformToken, "plt");
    },
  );
});

test("two per-contour tokens work without the shared one", () => {
  withEnv(
    { YANDEX_DELIVERY_EXPRESS_TOKEN: "exp", YANDEX_DELIVERY_PLATFORM_TOKEN: "plt" },
    () => {
      const config = loadConfig();
      assert.equal(config.expressToken, "exp");
      assert.equal(config.platformToken, "plt");
    },
  );
});

test("the platform base override points at the test contour", () => {
  withEnv(
    {
      YANDEX_DELIVERY_TOKEN: "shared",
      YANDEX_DELIVERY_PLATFORM_BASE_URL: "https://b2b.taxi.tst.yandex.net",
      YANDEX_DELIVERY_LANG: "en",
    },
    () => {
      const config = loadConfig();
      assert.equal(config.platformBase, "https://b2b.taxi.tst.yandex.net");
      assert.equal(config.expressBase, "https://b2b.taxi.yandex.net");
      assert.equal(config.lang, "en");
    },
  );
});

test("garbage numbers fall back to the defaults", () => {
  withEnv(
    {
      YANDEX_DELIVERY_TOKEN: "shared",
      YANDEX_DELIVERY_TIMEOUT_MS: "soon",
      YANDEX_DELIVERY_MAX_RETRIES: "-5",
    },
    () => {
      const config = loadConfig();
      assert.equal(config.timeoutMs, 60_000);
      assert.equal(config.maxRetries, 3);
    },
  );
});
