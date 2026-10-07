import { test } from "node:test";
import assert from "node:assert/strict";
import { registerTrackingTools } from "./tracking.js";

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
    performerPosition: make("performerPosition"),
    trackingLinks: make("trackingLinks"),
    pointsEta: make("pointsEta"),
    courierPhone: make("courierPhone"),
    confirmationCode: make("confirmationCode"),
  };
  const tools: Record<string, Handler> = {};
  const server = {
    registerTool: (name: string, _cfg: unknown, handler: Handler) => {
      tools[name] = handler;
    },
  };
  registerTrackingTools(server as never, client as never);
  return { calls, tools };
}

test("registers the five tracking tools", () => {
  const { tools } = harness();
  assert.deepEqual(Object.keys(tools).sort(), [
    "get_confirmation_code",
    "get_courier_phone",
    "get_performer_position",
    "get_points_eta",
    "get_tracking_links",
  ]);
});

test("claim_id-only tools forward the id as a plain string", async () => {
  const { calls, tools } = harness();
  await tools.get_performer_position({ claim_id: "c1" });
  await tools.get_tracking_links({ claim_id: "c2" });
  await tools.get_points_eta({ claim_id: "c3" });
  await tools.get_confirmation_code({ claim_id: "c4" });
  assert.deepEqual(
    calls.map((c) => [c.method, c.params]),
    [
      ["performerPosition", "c1"],
      ["trackingLinks", "c2"],
      ["pointsEta", "c3"],
      ["confirmationCode", "c4"],
    ],
  );
});

test("get_courier_phone forwards claim_id and the optional point_id", async () => {
  const { calls, tools } = harness();
  await tools.get_courier_phone({ claim_id: "c5" });
  await tools.get_courier_phone({ claim_id: "c5", point_id: 7 });
  assert.equal(calls[0].method, "courierPhone");
  assert.deepEqual(calls[0].params, { claim_id: "c5", point_id: undefined });
  assert.deepEqual(calls[1].params, { claim_id: "c5", point_id: 7 });
});

test("a client error is returned as an isError result, not thrown", async () => {
  const { tools } = harness({ throwOn: "pointsEta" });
  const res = await tools.get_points_eta({ claim_id: "c1" });
  assert.equal(res.isError, true);
  assert.match(res.content[0].text, /boom/);
});
