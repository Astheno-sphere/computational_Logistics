import { test } from "node:test";
import assert from "node:assert/strict";
import { registerClaimsTools } from "./claims.js";

type Args = Record<string, unknown>;
type Handler = (args: Args) => Promise<{ content: { text: string }[]; isError?: boolean }>;

/** Fake server + fake client so the tool handlers run without network. */
function harness(opts: { throwOn?: string } = {}) {
  const calls: { method: string; params: unknown }[] = [];
  const make =
    (method: string) =>
    async (...params: unknown[]) => {
      calls.push({ method, params: params.length === 1 ? params[0] : params });
      if (opts.throwOn === method) throw new Error("boom");
      return { ok: true };
    };
  const client = {
    checkPrice: make("checkPrice"),
    createClaim: make("createClaim"),
    getClaim: make("getClaim"),
    acceptClaim: make("acceptClaim"),
    cancelInfo: make("cancelInfo"),
    cancelClaim: make("cancelClaim"),
    searchClaims: make("searchClaims"),
  };
  const tools: Record<string, Handler> = {};
  const server = {
    registerTool: (name: string, _cfg: unknown, handler: Handler) => {
      tools[name] = handler;
    },
  };
  registerClaimsTools(server as never, client as never);
  return { calls, tools };
}

test("registers the seven claim-lifecycle tools", () => {
  const { tools } = harness();
  assert.deepEqual(Object.keys(tools).sort(), [
    "accept_claim",
    "cancel_claim",
    "check_price",
    "create_claim",
    "get_cancel_info",
    "get_claim",
    "search_claims",
  ]);
});

test("check_price forwards the whole body to client.checkPrice", async () => {
  const { calls, tools } = harness();
  const args = {
    route_points: [{ fullname: "Tashkent" }],
    items: [{ quantity: 1 }],
    skip_door_to_door: true,
  };
  await tools.check_price(args);
  assert.equal(calls[0].method, "checkPrice");
  assert.deepEqual(calls[0].params, args);
});

test("create_claim splits request_id from the claim body", async () => {
  const { calls, tools } = harness();
  await tools.create_claim({
    request_id: "token-1",
    items: [{ title: "Flowers", quantity: 1, cost_value: "350.00", cost_currency: "UZS" }],
    route_points: [{ point_id: 1 }, { point_id: 2 }],
    client_requirements: { taxi_class: "courier" },
    auto_accept: true,
  });
  assert.equal(calls[0].method, "createClaim");
  assert.deepEqual(calls[0].params, {
    request_id: "token-1",
    body: {
      items: [{ title: "Flowers", quantity: 1, cost_value: "350.00", cost_currency: "UZS" }],
      route_points: [{ point_id: 1 }, { point_id: 2 }],
      client_requirements: { taxi_class: "courier" },
      auto_accept: true,
    },
  });
});

test("claim_id-only tools forward the id as a plain string", async () => {
  const { calls, tools } = harness();
  await tools.get_claim({ claim_id: "c1" });
  await tools.get_cancel_info({ claim_id: "c2" });
  assert.deepEqual(
    calls.map((c) => [c.method, c.params]),
    [
      ["getClaim", "c1"],
      ["cancelInfo", "c2"],
    ],
  );
});

test("accept and cancel forward version and cancel_state", async () => {
  const { calls, tools } = harness();
  await tools.accept_claim({ claim_id: "c1", version: 1 });
  await tools.cancel_claim({ claim_id: "c1", version: 2, cancel_state: "free" });
  assert.deepEqual(calls[0].params, { claim_id: "c1", version: 1 });
  assert.deepEqual(calls[1].params, { claim_id: "c1", version: 2, cancel_state: "free" });
});

test("search_claims forwards the filters verbatim", async () => {
  const { calls, tools } = harness();
  await tools.search_claims({ limit: 5, status: "delivered" });
  assert.equal(calls[0].method, "searchClaims");
  assert.deepEqual(calls[0].params, { limit: 5, status: "delivered" });
});

test("a client error is returned as an isError result, not thrown", async () => {
  const { tools } = harness({ throwOn: "acceptClaim" });
  const res = await tools.accept_claim({ claim_id: "c1", version: 1 });
  assert.equal(res.isError, true);
  assert.match(res.content[0].text, /boom/);
});
