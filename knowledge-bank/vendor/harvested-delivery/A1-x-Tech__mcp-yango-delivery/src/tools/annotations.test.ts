import { test } from "node:test";
import assert from "node:assert/strict";
import { registerClaimsTools } from "./claims.js";
import { registerTrackingTools } from "./tracking.js";
import { registerRawTool } from "./raw.js";
import { DESTRUCTIVE, READ_ONLY, WRITE } from "./util.js";

interface Annotations {
  readOnlyHint?: boolean;
  destructiveHint?: boolean;
  idempotentHint?: boolean;
  openWorldHint?: boolean;
}

/** Registers every tool against a fake server, capturing each tool's annotations. */
function collectAnnotations(): Record<string, Annotations | undefined> {
  const annotations: Record<string, Annotations | undefined> = {};
  const server = {
    registerTool: (name: string, cfg: { annotations?: Annotations }) => {
      annotations[name] = cfg.annotations;
    },
  };
  // Registration reads the client only inside handlers, so a stub is fine here.
  registerClaimsTools(server as never, {} as never);
  registerTrackingTools(server as never, {} as never);
  registerRawTool(server as never, {} as never);
  return annotations;
}

const ANN = collectAnnotations();

/**
 * Yango Delivery is a write API, so this is a per-tool map, not a single
 * invariant: reads are READ_ONLY, state-changing calls are WRITE and
 * cancellation (plus the raw escape hatch) is DESTRUCTIVE. Adding a tool
 * means adding it here consciously.
 */
const EXPECTED: Record<string, Annotations> = {
  check_price: READ_ONLY,
  create_claim: WRITE,
  get_claim: READ_ONLY,
  accept_claim: WRITE,
  get_cancel_info: READ_ONLY,
  cancel_claim: DESTRUCTIVE,
  search_claims: READ_ONLY,
  get_performer_position: READ_ONLY,
  get_tracking_links: READ_ONLY,
  get_points_eta: READ_ONLY,
  get_courier_phone: READ_ONLY,
  get_confirmation_code: READ_ONLY,
  raw_request: DESTRUCTIVE,
};

test("registers all thirteen tools with annotations", () => {
  assert.deepEqual(Object.keys(ANN).sort(), Object.keys(EXPECTED).sort());
  for (const [name, a] of Object.entries(ANN)) {
    assert.ok(a, `${name} is missing annotations`);
  }
});

test("every tool carries its expected hints, all four set explicitly", () => {
  for (const [name, expected] of Object.entries(EXPECTED)) {
    assert.deepEqual(ANN[name], expected, `${name} annotations drifted`);
  }
});

test("no read-only tool is marked destructive and vice versa", () => {
  for (const [name, a] of Object.entries(ANN)) {
    if (a?.readOnlyHint) {
      assert.equal(a.destructiveHint, false, `${name}: a read cannot be destructive`);
      assert.equal(a.idempotentHint, true, `${name}: re-reading yields the same result`);
    } else {
      assert.equal(a?.idempotentHint, false, `${name}: writes are not idempotent for the client`);
    }
    assert.equal(a?.openWorldHint, true, `${name} should set openWorldHint`);
  }
});
