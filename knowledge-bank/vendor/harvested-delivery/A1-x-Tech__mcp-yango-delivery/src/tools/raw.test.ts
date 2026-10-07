import { test } from "node:test";
import assert from "node:assert/strict";
import { DeliveryClient } from "../client.js";
import { registerRawTool } from "./raw.js";

type Args = Record<string, unknown>;
type Handler = (args: Args) => Promise<{ content: { text: string }[]; isError?: boolean }>;

/** Registers raw_request against a real client with a recording fetch stub. */
function harness() {
  const original = globalThis.fetch;
  const calls: { url: string; method: string; auth: unknown; body: unknown }[] = [];
  globalThis.fetch = (async (url: unknown, init: unknown) => {
    const i = (init ?? {}) as { method: string; headers: Record<string, string>; body?: string };
    calls.push({
      url: String(url),
      method: i.method,
      auth: i.headers.Authorization,
      body: i.body ? JSON.parse(i.body) : undefined,
    });
    return new Response(JSON.stringify({ ok: true }), { status: 200 });
  }) as typeof fetch;

  const client = new DeliveryClient({
    token: "TOK",
    baseUrl: "https://b2b.taxi.yandex.net",
    lang: "en",
    maxRetries: 0,
  });
  const tools: Record<string, Handler> = {};
  const server = {
    registerTool: (name: string, _cfg: unknown, h: Handler) => {
      tools[name] = h;
    },
  };
  registerRawTool(server as never, client);
  return {
    tools,
    calls,
    restore: () => {
      globalThis.fetch = original;
    },
  };
}

test("raw_request defaults to POST and sends the body as JSON", async () => {
  const { tools, calls, restore } = harness();
  try {
    const res = await tools.raw_request({
      path: "b2b/cargo/integration/v2/claims/bulk_info",
      body: { claim_ids: ["c1"] },
    });
    assert.equal(res.isError, undefined);
    assert.equal(calls[0].method, "POST");
    assert.equal(calls[0].url, "https://b2b.taxi.yandex.net/b2b/cargo/integration/v2/claims/bulk_info");
    assert.equal(calls[0].auth, "Bearer TOK");
    assert.deepEqual(calls[0].body, { claim_ids: ["c1"] });
  } finally {
    restore();
  }
});

test("raw_request supports GET with query parameters and no body", async () => {
  const { tools, calls, restore } = harness();
  try {
    await tools.raw_request({
      path: "b2b/cargo/integration/v2/claims/tracking-links",
      method: "GET",
      query: { claim_id: "c1" },
    });
    assert.equal(calls[0].method, "GET");
    assert.equal(
      calls[0].url,
      "https://b2b.taxi.yandex.net/b2b/cargo/integration/v2/claims/tracking-links?claim_id=c1",
    );
    assert.equal(calls[0].body, undefined);
  } finally {
    restore();
  }
});

test("raw_request rejects an absolute path as an isError result, without fetching", async () => {
  for (const evil of ["https://evil.example/steal", "http://evil.example/x", "\\\\evil.example/x"]) {
    const { tools, calls, restore } = harness();
    try {
      const res = await tools.raw_request({ path: evil, body: {} });
      assert.equal(res.isError, true, `${JSON.stringify(evil)} should be isError`);
      assert.match(res.content[0].text, /foreign origin/);
      assert.equal(calls.length, 0, `must not fetch for ${JSON.stringify(evil)}`);
    } finally {
      restore();
    }
  }
});
