import { test } from "node:test";
import assert from "node:assert/strict";
import { DeliveryClient } from "./client.js";
import { CredentialsError } from "./types.js";
import type { DeliveryConfig } from "./types.js";

const BASE = "https://b2b.taxi.yandex.net";

type Call = {
  url: string;
  method: string;
  auth: unknown;
  lang: unknown;
  body: Record<string, unknown> | undefined;
};

function makeConfig(extra: Partial<DeliveryConfig> = {}): DeliveryConfig {
  return {
    token: "TOK",
    baseUrl: BASE,
    lang: "en",
    maxRetries: 0,
    retryBaseMs: 0, // no real backoff delay in tests
    ...extra,
  };
}

/** Installs a recording fetch stub and returns a client + the captured calls. */
function harness(extra: Partial<DeliveryConfig> = {}) {
  const calls: Call[] = [];
  const orig = globalThis.fetch;
  globalThis.fetch = (async (
    url: unknown,
    init: { method: string; headers: Record<string, string>; body?: string },
  ) => {
    calls.push({
      url: String(url),
      method: init.method,
      auth: init.headers.Authorization,
      lang: init.headers["Accept-Language"],
      body: init.body ? JSON.parse(init.body) : undefined,
    });
    return new Response(JSON.stringify({ ok: true }), { status: 200 });
  }) as typeof fetch;

  return {
    client: new DeliveryClient(makeConfig(extra)),
    calls,
    restore: () => {
      globalThis.fetch = orig;
    },
  };
}

// --- Endpoint mapping ---

test("checkPrice: check-price path, Bearer token, Accept-Language, compact body", async () => {
  const { client, calls, restore } = harness();
  try {
    await client.checkPrice({
      route_points: [{ fullname: "Tashkent, Amir Timur Avenue, 107" }],
      items: [{ quantity: 1, weight: 2 }],
      requirements: undefined,
    });
  } finally {
    restore();
  }
  assert.equal(calls[0].url, `${BASE}/b2b/cargo/integration/v2/check-price`);
  assert.equal(calls[0].method, "POST");
  assert.equal(calls[0].auth, "Bearer TOK");
  assert.equal(calls[0].lang, "en");
  assert.deepEqual(calls[0].body, {
    route_points: [{ fullname: "Tashkent, Amir Timur Avenue, 107" }],
    items: [{ quantity: 1, weight: 2 }],
  });
});

test("createClaim: request_id rides in the query, the body passes through", async () => {
  const { client, calls, restore } = harness();
  try {
    await client.createClaim({
      request_id: "my-token-1",
      body: { items: [{ title: "Flowers" }], comment: undefined },
    });
  } finally {
    restore();
  }
  assert.equal(calls[0].url, `${BASE}/b2b/cargo/integration/v2/claims/create?request_id=my-token-1`);
  assert.deepEqual(calls[0].body, { items: [{ title: "Flowers" }] });
});

test("createClaim mints a UUID request_id when the caller omits it", async () => {
  const { client, calls, restore } = harness();
  try {
    await client.createClaim({ body: { items: [] } });
  } finally {
    restore();
  }
  const requestId = new URL(calls[0].url).searchParams.get("request_id");
  assert.match(
    requestId ?? "",
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
    "an auto-minted request_id must be a UUID",
  );
});

test("getClaim: claim_id in the query, an empty body by contract", async () => {
  const { client, calls, restore } = harness();
  try {
    await client.getClaim("claim-123");
  } finally {
    restore();
  }
  assert.equal(calls[0].url, `${BASE}/b2b/cargo/integration/v2/claims/info?claim_id=claim-123`);
  assert.equal(calls[0].method, "POST");
  assert.equal(calls[0].body, undefined);
});

test("acceptClaim sends the version in the body", async () => {
  const { client, calls, restore } = harness();
  try {
    await client.acceptClaim({ claim_id: "c1", version: 2 });
  } finally {
    restore();
  }
  assert.equal(calls[0].url, `${BASE}/b2b/cargo/integration/v2/claims/accept?claim_id=c1`);
  assert.deepEqual(calls[0].body, { version: 2 });
});

test("cancelInfo: claim_id in the query, no body", async () => {
  const { client, calls, restore } = harness();
  try {
    await client.cancelInfo("c1");
  } finally {
    restore();
  }
  assert.equal(calls[0].url, `${BASE}/b2b/cargo/integration/v2/claims/cancel-info?claim_id=c1`);
  assert.equal(calls[0].body, undefined);
});

test("cancelClaim sends version + cancel_state in the body", async () => {
  const { client, calls, restore } = harness();
  try {
    await client.cancelClaim({ claim_id: "c1", version: 3, cancel_state: "paid" });
  } finally {
    restore();
  }
  assert.equal(calls[0].url, `${BASE}/b2b/cargo/integration/v2/claims/cancel?claim_id=c1`);
  assert.deepEqual(calls[0].body, { version: 3, cancel_state: "paid" });
});

test("searchClaims compacts the filters", async () => {
  const { client, calls, restore } = harness();
  try {
    await client.searchClaims({ limit: 10, status: "delivered", phone: undefined });
  } finally {
    restore();
  }
  assert.equal(calls[0].url, `${BASE}/b2b/cargo/integration/v2/claims/search`);
  assert.deepEqual(calls[0].body, { limit: 10, status: "delivered" });
});

test("performerPosition and trackingLinks are GETs with claim_id and no body", async () => {
  const { client, calls, restore } = harness();
  try {
    await client.performerPosition("c9");
    await client.trackingLinks("c9");
  } finally {
    restore();
  }
  assert.equal(calls[0].url, `${BASE}/b2b/cargo/integration/v2/claims/performer-position?claim_id=c9`);
  assert.equal(calls[0].method, "GET");
  assert.equal(calls[0].body, undefined);
  assert.equal(calls[1].url, `${BASE}/b2b/cargo/integration/v2/claims/tracking-links?claim_id=c9`);
  assert.equal(calls[1].method, "GET");
});

test("pointsEta: POST with claim_id in the query and no body", async () => {
  const { client, calls, restore } = harness();
  try {
    await client.pointsEta("c5");
  } finally {
    restore();
  }
  assert.equal(calls[0].url, `${BASE}/b2b/cargo/integration/v2/claims/points-eta?claim_id=c5`);
  assert.equal(calls[0].method, "POST");
  assert.equal(calls[0].body, undefined);
});

test("courierPhone: claim_id (and optional point_id) ride in the body", async () => {
  const { client, calls, restore } = harness();
  try {
    await client.courierPhone({ claim_id: "c6" });
    await client.courierPhone({ claim_id: "c6", point_id: 42 });
  } finally {
    restore();
  }
  assert.equal(calls[0].url, `${BASE}/b2b/cargo/integration/v2/driver-voiceforwarding`);
  assert.deepEqual(calls[0].body, { claim_id: "c6" });
  assert.deepEqual(calls[1].body, { claim_id: "c6", point_id: 42 });
});

test("confirmationCode: claim_id rides in the body (underscore path)", async () => {
  const { client, calls, restore } = harness();
  try {
    await client.confirmationCode("c7");
  } finally {
    restore();
  }
  assert.equal(calls[0].url, `${BASE}/b2b/cargo/integration/v2/claims/confirmation_code`);
  assert.equal(calls[0].method, "POST");
  assert.deepEqual(calls[0].body, { claim_id: "c7" });
});

// --- Errors / retry / timeout / SSRF behavior ---

function mockFetch(handler: (url: string, init: RequestInit) => Response | Promise<Response>) {
  const original = globalThis.fetch;
  const calls: { url: string; init: RequestInit }[] = [];
  globalThis.fetch = (async (url: unknown, init: unknown) => {
    const i = (init ?? {}) as RequestInit;
    calls.push({ url: String(url), init: i });
    return handler(String(url), i);
  }) as typeof fetch;
  return {
    calls,
    restore() {
      globalThis.fetch = original;
    },
  };
}

function makeClient(overrides: Partial<DeliveryConfig> = {}) {
  return new DeliveryClient(makeConfig(overrides));
}

test("non-2xx throws DeliveryError with the {code, message} body decoded", async () => {
  const mock = mockFetch(
    () => new Response(JSON.stringify({ code: "not_found", message: "claim not found" }), { status: 404 }),
  );
  try {
    await assert.rejects(() => makeClient().getClaim("nope"), /HTTP 404: \[not_found\] claim not found/);
  } finally {
    mock.restore();
  }
});

test("request() retries a 429 even for a non-idempotent write", async () => {
  let calls = 0;
  const mock = mockFetch(() => {
    calls++;
    if (calls === 1) return new Response("rate limited", { status: 429 });
    return new Response(JSON.stringify({ ok: true }), { status: 200 });
  });
  try {
    const result = await makeClient({ maxRetries: 3 }).acceptClaim({ claim_id: "c1", version: 1 });
    assert.deepEqual(result, { ok: true });
    assert.equal(calls, 2);
  } finally {
    mock.restore();
  }
});

test("request() does NOT retry a 5xx for a non-idempotent write", async () => {
  let calls = 0;
  const mock = mockFetch(() => {
    calls++;
    return new Response("boom", { status: 502 });
  });
  try {
    await assert.rejects(
      () => makeClient({ maxRetries: 3 }).acceptClaim({ claim_id: "c1", version: 1 }),
      /HTTP 502/,
    );
    assert.equal(calls, 1, "a write must not be replayed after a 5xx");
  } finally {
    mock.restore();
  }
});

test("request() retries a 5xx for an idempotent read", async () => {
  let calls = 0;
  const mock = mockFetch(() => {
    calls++;
    if (calls === 1) return new Response("unavailable", { status: 503 });
    return new Response(JSON.stringify({ ok: true }), { status: 200 });
  });
  try {
    const result = await makeClient({ maxRetries: 3 }).getClaim("c1");
    assert.deepEqual(result, { ok: true });
    assert.equal(calls, 2);
  } finally {
    mock.restore();
  }
});

test("request() retries a 5xx for claims/create (request_id makes it idempotent)", async () => {
  let calls = 0;
  const urls: string[] = [];
  const mock = mockFetch((url) => {
    calls++;
    urls.push(url);
    if (calls === 1) return new Response("bad gateway", { status: 502 });
    return new Response(JSON.stringify({ id: "c1" }), { status: 200 });
  });
  try {
    const result = await makeClient({ maxRetries: 3 }).createClaim({ body: { items: [] } });
    assert.deepEqual(result, { id: "c1" });
    assert.equal(calls, 2);
    assert.equal(urls[0], urls[1], "the retry must reuse the same request_id");
  } finally {
    mock.restore();
  }
});

test("request() retries a network error for reads and rethrows it for writes", async () => {
  let calls = 0;
  const mock = mockFetch(() => {
    calls++;
    if (calls === 1) throw new Error("ECONNRESET");
    return new Response(JSON.stringify({ ok: true }), { status: 200 });
  });
  try {
    const result = await makeClient({ maxRetries: 3 }).searchClaims({});
    assert.deepEqual(result, { ok: true });
    assert.equal(calls, 2);
  } finally {
    mock.restore();
  }

  calls = 0;
  const mock2 = mockFetch(() => {
    calls++;
    throw new Error("ECONNRESET");
  });
  try {
    await assert.rejects(
      () => makeClient({ maxRetries: 3 }).cancelClaim({ claim_id: "c1", version: 1, cancel_state: "free" }),
      /ECONNRESET/,
    );
    assert.equal(calls, 1, "a write must not be replayed after a network error");
  } finally {
    mock2.restore();
  }
});

test("request() does not retry a 400 and gives up after maxRetries on 429", async () => {
  let calls = 0;
  const mock = mockFetch(() => {
    calls++;
    return new Response("nope", { status: 400 });
  });
  try {
    await assert.rejects(() => makeClient().getClaim("c1"), /HTTP 400/);
    assert.equal(calls, 1);
  } finally {
    mock.restore();
  }

  calls = 0;
  const mock2 = mockFetch(() => {
    calls++;
    return new Response("slow down", { status: 429 });
  });
  try {
    await assert.rejects(() => makeClient({ maxRetries: 2 }).getClaim("c1"), /HTTP 429/);
    assert.equal(calls, 3); // initial + 2 retries
  } finally {
    mock2.restore();
  }
});

test("request() aborts and reports a timeout when the request hangs", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = ((_url: unknown, init: unknown) =>
    new Promise((_resolve, reject) => {
      const signal = (init as RequestInit).signal as AbortSignal;
      signal.addEventListener("abort", () =>
        reject(Object.assign(new Error("aborted"), { name: "AbortError" })),
      );
    })) as typeof fetch;
  try {
    const client = makeClient({ timeoutMs: 10, maxRetries: 0 });
    await assert.rejects(() => client.getClaim("c1"), /timed out after 10ms/);
  } finally {
    globalThis.fetch = original;
  }
});

test("request() rejects an absolute path (SSRF) without fetching", async () => {
  for (const evil of ["https://evil.example/steal", "http://evil.example/x", "\\\\evil.example/x"]) {
    const mock = mockFetch(() => new Response("{}", { status: 200 }));
    try {
      await assert.rejects(() => makeClient().request("POST", evil, { body: {} }), /foreign origin/);
      assert.equal(mock.calls.length, 0, `must not fetch for ${JSON.stringify(evil)}`);
    } finally {
      mock.restore();
    }
  }
});

// --- Missing credentials (degraded start) ---

// The exact startup-era text, relayed verbatim at call time — pinned so a
// reworded message does not silently change what the model tells the user.
const MISSING_TOKEN_TEXT =
  'YANGO_DELIVERY_TOKEN is required (OAuth token from the delivery cabinet, Integration tab -> "Get token").';

test("request() without a token throws CredentialsError; fetch is never called", async () => {
  const mock = mockFetch(() => new Response("{}", { status: 200 }));
  try {
    const client = new DeliveryClient({ baseUrl: BASE, lang: "en" });
    await assert.rejects(
      () => client.getClaim("c1"),
      (err: unknown) => {
        assert.ok(err instanceof CredentialsError, "must be a CredentialsError");
        assert.equal((err as Error).name, "CredentialsError");
        const message = (err as Error).message;
        assert.ok(
          message.startsWith(MISSING_TOKEN_TEXT),
          `message must open with the exact startup text, got: ${message}`,
        );
        assert.match(message, /restart the server/, "and say the server needs a restart");
        return true;
      },
    );
    // Not transport trouble: the retry/backoff branch — and fetch itself —
    // must never run for a configuration problem.
    assert.equal(mock.calls.length, 0, "fetch must not be called without credentials");
  } finally {
    mock.restore();
  }
});

test("request() still accepts relative API paths (with or without a leading slash)", async () => {
  const mock = mockFetch(() => new Response(JSON.stringify({ ok: true }), { status: 200 }));
  try {
    await makeClient().request("POST", "b2b/cargo/integration/v2/claims/search", { body: {} });
    await makeClient().request("GET", "/b2b/cargo/integration/v2/claims/tracking-links", {
      query: { claim_id: "c1" },
    });
    assert.equal(mock.calls[0].url, `${BASE}/b2b/cargo/integration/v2/claims/search`);
    assert.equal(mock.calls[1].url, `${BASE}/b2b/cargo/integration/v2/claims/tracking-links?claim_id=c1`);
  } finally {
    mock.restore();
  }
});
