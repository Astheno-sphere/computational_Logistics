import { test } from "node:test";
import assert from "node:assert/strict";
import { registerPlatformTools } from "./platform.js";

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
    listPickupPoints: make("listPickupPoints"),
    createOffers: make("createOffers"),
    confirmOffer: make("confirmOffer"),
    getRequest: make("getRequest"),
    requestHistory: make("requestHistory"),
    cancelRequest: make("cancelRequest"),
  };
  const tools: Record<string, Handler> = {};
  const server = {
    registerTool: (name: string, _cfg: unknown, handler: Handler) => {
      tools[name] = handler;
    },
  };
  registerPlatformTools(server as never, client as never);
  return { calls, tools };
}

test("registers the six platform tools", () => {
  const { tools } = harness();
  assert.deepEqual(Object.keys(tools).sort(), [
    "platform_cancel_request",
    "platform_confirm_offer",
    "platform_create_offers",
    "platform_get_request",
    "platform_list_pickup_points",
    "platform_request_history",
  ]);
});

test("platform_list_pickup_points forwards the filters", async () => {
  const { calls, tools } = harness();
  await tools.platform_list_pickup_points({ geo_id: 213, type: "terminal" });
  assert.equal(calls[0].method, "listPickupPoints");
  assert.deepEqual(calls[0].params, { geo_id: 213, type: "terminal" });
});

test("platform_create_offers forwards the whole order payload", async () => {
  const { calls, tools } = harness();
  const args = {
    info: { operator_request_id: "order-1" },
    source: { platform_station: { platform_id: "st-1" } },
    destination: { platform_station: { platform_id: "pvz-1" } },
    items: [{ count: 1, name: "Книга" }],
    places: [{ barcode: "BOX-1" }],
    billing_info: { payment_method: "already_paid" },
    recipient_info: { first_name: "Иван", phone: "+79991234567" },
    last_mile_policy: "self_pickup",
  };
  await tools.platform_create_offers(args);
  assert.equal(calls[0].method, "createOffers");
  assert.deepEqual(calls[0].params, args);
});

test("platform_confirm_offer forwards the offer id as a plain string", async () => {
  const { calls, tools } = harness();
  await tools.platform_confirm_offer({ offer_id: "offer-42" });
  assert.deepEqual(calls[0], { method: "confirmOffer", params: "offer-42" });
});

test("platform_get_request forwards request_id, request_code and slim", async () => {
  const { calls, tools } = harness();
  await tools.platform_get_request({ request_id: "r-1", slim: true });
  assert.equal(calls[0].method, "getRequest");
  assert.deepEqual(calls[0].params, { request_id: "r-1", request_code: undefined, slim: true });
});

test("history and cancel forward the request id as a plain string", async () => {
  const { calls, tools } = harness();
  await tools.platform_request_history({ request_id: "r-2" });
  await tools.platform_cancel_request({ request_id: "r-3" });
  assert.deepEqual(calls[0], { method: "requestHistory", params: "r-2" });
  assert.deepEqual(calls[1], { method: "cancelRequest", params: "r-3" });
});

test("a client error is returned as an isError result, not thrown", async () => {
  const { tools } = harness({ throwOn: "confirmOffer" });
  const res = await tools.platform_confirm_offer({ offer_id: "offer-1" });
  assert.equal(res.isError, true);
  assert.match(res.content[0].text, /boom/);
});
