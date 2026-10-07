import { test } from "node:test";
import assert from "node:assert/strict";
import { registerExpressTools } from "./express.js";

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
    performerPosition: make("performerPosition"),
    trackingLinks: make("trackingLinks"),
  };
  const tools: Record<string, Handler> = {};
  const server = {
    registerTool: (name: string, _cfg: unknown, handler: Handler) => {
      tools[name] = handler;
    },
  };
  registerExpressTools(server as never, client as never);
  return { calls, tools };
}

test("registers the nine express tools", () => {
  const { tools } = harness();
  assert.deepEqual(Object.keys(tools).sort(), [
    "express_accept_claim",
    "express_cancel_claim",
    "express_cancel_info",
    "express_check_price",
    "express_create_claim",
    "express_get_claim",
    "express_performer_position",
    "express_search_claims",
    "express_tracking_links",
  ]);
});

test("express_check_price forwards the whole body to client.checkPrice", async () => {
  const { calls, tools } = harness();
  const args = {
    route_points: [{ fullname: "Москва" }],
    items: [{ quantity: 1 }],
    skip_door_to_door: true,
  };
  await tools.express_check_price(args);
  assert.equal(calls[0].method, "checkPrice");
  assert.deepEqual(calls[0].params, args);
});

test("express_create_claim splits request_id from the claim body", async () => {
  const { calls, tools } = harness();
  await tools.express_create_claim({
    request_id: "token-1",
    items: [{ title: "Букет", quantity: 1, cost_value: "350.00", cost_currency: "RUB" }],
    route_points: [{ point_id: 1 }, { point_id: 2 }],
    client_requirements: { taxi_class: "courier" },
    auto_accept: true,
  });
  assert.equal(calls[0].method, "createClaim");
  assert.deepEqual(calls[0].params, {
    request_id: "token-1",
    body: {
      items: [{ title: "Букет", quantity: 1, cost_value: "350.00", cost_currency: "RUB" }],
      route_points: [{ point_id: 1 }, { point_id: 2 }],
      client_requirements: { taxi_class: "courier" },
      auto_accept: true,
    },
  });
});

test("claim_id-only tools forward the id as a plain string", async () => {
  const { calls, tools } = harness();
  await tools.express_get_claim({ claim_id: "c1" });
  await tools.express_cancel_info({ claim_id: "c2" });
  await tools.express_performer_position({ claim_id: "c3" });
  await tools.express_tracking_links({ claim_id: "c4" });
  assert.deepEqual(
    calls.map((c) => [c.method, c.params]),
    [
      ["getClaim", "c1"],
      ["cancelInfo", "c2"],
      ["performerPosition", "c3"],
      ["trackingLinks", "c4"],
    ],
  );
});

test("accept and cancel forward version and cancel_state", async () => {
  const { calls, tools } = harness();
  await tools.express_accept_claim({ claim_id: "c1", version: 1 });
  await tools.express_cancel_claim({ claim_id: "c1", version: 2, cancel_state: "free" });
  assert.deepEqual(calls[0].params, { claim_id: "c1", version: 1 });
  assert.deepEqual(calls[1].params, { claim_id: "c1", version: 2, cancel_state: "free" });
});

test("express_search_claims forwards the filters verbatim", async () => {
  const { calls, tools } = harness();
  await tools.express_search_claims({ limit: 5, status: "delivered" });
  assert.equal(calls[0].method, "searchClaims");
  assert.deepEqual(calls[0].params, { limit: 5, status: "delivered" });
});

test("a client error is returned as an isError result, not thrown", async () => {
  const { tools } = harness({ throwOn: "acceptClaim" });
  const res = await tools.express_accept_claim({ claim_id: "c1", version: 1 });
  assert.equal(res.isError, true);
  assert.match(res.content[0].text, /boom/);
});
