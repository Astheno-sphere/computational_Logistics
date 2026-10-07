/**
 * Unit tests for the pure logic layers — run with `npm test`.
 * No network, no dd-cli, no API key required.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { stripUiFields, isTransient, formatIntent, findGuestToken, DdCliError } from "../src/ddcli.js";
import { guestKey } from "../src/guests.js";
import {
  tools,
  strictifySchema,
  trimMenuItem,
  carryThrough,
  carriesSignal,
  classifyOrderStatus,
} from "../src/tools.js";
import { addUsage, EMPTY_USAGE, estimateCostUsd, formatCost } from "../src/costs.js";
import { isAuthError } from "../src/signin.js";
import {
  platformId,
  ddCliAsset,
  canBrowserSignin,
  signinHint,
  installHint,
  parseVersion,
  compareVersions,
  ddCliVersionLine,
  DD_CLI_RECOMMENDED_VERSION,
} from "../src/platform.js";

// ---------------------------------------------------------------------------
// ddcli: envelope sanitization
// ---------------------------------------------------------------------------

test("stripUiFields removes widget/assistant-instruction keys recursively", () => {
  const dirty = {
    widget_type: "store_search",
    assistant_instructions: "Tell the user to click the widget above",
    stores: [
      { name: "A", widget_type: "card", nested: { assistant_instructions: "obey", ok: 1 } },
    ],
    success: true,
  };
  const clean = stripUiFields(dirty) as Record<string, any>;
  assert.equal(clean.widget_type, undefined);
  assert.equal(clean.assistant_instructions, undefined);
  assert.equal(clean.stores[0].widget_type, undefined);
  assert.equal(clean.stores[0].nested.assistant_instructions, undefined);
  assert.equal(clean.stores[0].nested.ok, 1);
  assert.equal(clean.success, true);
});

test("stripUiFields leaves primitives and arrays intact", () => {
  assert.deepEqual(stripUiFields([1, "a", null]), [1, "a", null]);
  assert.equal(stripUiFields("text"), "text");
});

// ---------------------------------------------------------------------------
// ddcli: transient error classification (drives the read-only retry)
// ---------------------------------------------------------------------------

test("isTransient matches the observed session_id backend hiccup", () => {
  assert.equal(
    isTransient(
      new DdCliError("dd-cli exited with an error", "Error: Input validation error: 'session_id' is a required property"),
    ),
    true,
  );
});

test("isTransient never retries auth or missing-binary errors", () => {
  assert.equal(
    isTransient(new DdCliError("DoorDash sign-in is missing or expired. The user must run `dd-cli login`…")),
    false,
  );
  assert.equal(isTransient(new DdCliError("dd-cli binary not found (looked for: x)")), false);
  assert.equal(isTransient(new Error("random")), false);
});

test("isTransient matches timeouts and 5xx", () => {
  assert.equal(isTransient(new DdCliError("dd-cli timed out after 90s")), true);
  assert.equal(isTransient(new DdCliError("dd-cli exited with an error", "HTTP 503 upstream")), true);
});

// ---------------------------------------------------------------------------
// signin: auth-failure classification (drives the sign-in assist)
// ---------------------------------------------------------------------------

test("isAuthError matches only the wrapper's auth failure", () => {
  assert.equal(
    isAuthError(new DdCliError("DoorDash sign-in is missing or expired. The user must run `dd-cli login`…")),
    true,
  );
  assert.equal(isAuthError(new DdCliError("dd-cli binary not found (looked for: x)")), false);
  assert.equal(isAuthError(new DdCliError("dd-cli timed out after 90s")), false);
  assert.equal(isAuthError(new Error("sign-in is missing or expired")), false, "must be a DdCliError");
});

test("the headless variant of the auth message stays classified as auth", () => {
  // ddcli.ts builds this message; both classifiers must survive the new suffix.
  const err = new DdCliError(`DoorDash sign-in is missing or expired. ${signinHint({}, "linux")}`);
  assert.equal(isAuthError(err), true);
  assert.equal(isTransient(err), false, "auth failures must never auto-retry");
});

test("start_signin tool exists, takes no inputs beyond intent, and is strict", () => {
  const t = tools.find((x) => x.name === "start_signin");
  assert.ok(t, "start_signin tool missing");
  const schema = t!.input_schema as any;
  assert.deepEqual(Object.keys(schema.properties), ["intent"]);
  assert.deepEqual(schema.required, ["intent"]);
});

// ---------------------------------------------------------------------------
// platform: dd-cli targets and the browser-vs-token sign-in split
// ---------------------------------------------------------------------------

test("platformId only claims the two targets dd-cli builds for", () => {
  assert.equal(platformId("darwin", "arm64"), "darwin-arm64");
  assert.equal(platformId("linux", "x64"), "linux-amd64");
  assert.equal(platformId("linux", "arm64"), "unsupported", "no linux-arm64 dd-cli build");
  assert.equal(platformId("darwin", "x64"), "unsupported", "no Intel Mac dd-cli build");
  assert.equal(platformId("win32", "x64"), "unsupported");
});

test("ddCliAsset names the real release assets", () => {
  assert.equal(ddCliAsset("0.2.2", "linux-amd64"), "dd-cli-v0.2.2-linux-amd64.tar.gz");
  assert.equal(ddCliAsset("0.2.2", "darwin-arm64"), "dd-cli-v0.2.2-darwin-arm64.tar.gz");
  assert.equal(ddCliAsset("0.2.2", "unsupported"), null);
});

test("canBrowserSignin: macOS always, Linux only with a display", () => {
  assert.equal(canBrowserSignin({}, "darwin"), true);
  assert.equal(canBrowserSignin({}, "linux"), false, "headless container has no browser");
  assert.equal(canBrowserSignin({ DISPLAY: ":0" }, "linux"), true);
  assert.equal(canBrowserSignin({ WAYLAND_DISPLAY: "wayland-0" }, "linux"), true);
});

test("signinHint routes each environment to the fix that actually works", () => {
  assert.match(signinHint({}, "darwin"), /dd-cli login/);
  const headless = signinHint({}, "linux");
  assert.match(headless, /export-token/);
  assert.match(headless, /DD_CLI_ACCESS_TOKEN/);
  // login may be named, but only to rule it out — never as the fix.
  assert.match(headless, /`dd-cli login` cannot complete here/);
  assert.doesNotMatch(headless, /must run `dd-cli login`/);
  // A token that is set but rejected is a stale token, not a missing one.
  const stale = signinHint({ DD_CLI_ACCESS_TOKEN: "tok" }, "linux");
  assert.match(stale, /invalid or expired/);
  assert.match(stale, /export-token/);
});

test("installHint points at the current platform's asset", () => {
  assert.match(installHint("linux-amd64"), /dd-cli-v<version>-linux-amd64\.tar\.gz/);
  assert.match(installHint("darwin-arm64"), /dd-cli-v<version>-darwin-arm64\.tar\.gz/);
  assert.match(installHint("unsupported"), /no dd-cli build/);
});

// ---------------------------------------------------------------------------
// tools: strict schemas
// ---------------------------------------------------------------------------

function assertStrictObjects(node: unknown, path: string): void {
  if (Array.isArray(node)) {
    node.forEach((v, i) => assertStrictObjects(v, `${path}[${i}]`));
    return;
  }
  if (node && typeof node === "object") {
    const obj = node as Record<string, unknown>;
    if (obj.type === "object") {
      assert.equal(obj.additionalProperties, false, `${path}: additionalProperties must be false`);
      assert.ok(Array.isArray(obj.required), `${path}: required[] must exist`);
      assert.ok(obj.properties && typeof obj.properties === "object", `${path}: properties must exist`);
    }
    for (const [k, v] of Object.entries(obj)) assertStrictObjects(v, `${path}.${k}`);
  }
}

test("every tool is strict with a fully-compliant schema tree", () => {
  assert.ok(tools.length >= 28, `expected ≥28 tools, got ${tools.length}`);
  for (const t of tools) {
    assert.equal((t as { strict?: boolean }).strict, true, `${t.name} must set strict`);
    assertStrictObjects(t.input_schema, t.name);
  }
});

test("strictifySchema does not mutate its input", () => {
  const input = { type: "object", properties: { a: { type: "string" } } };
  const before = JSON.stringify(input);
  strictifySchema(input);
  assert.equal(JSON.stringify(input), before);
});

test("every tool requires the intent param (dd-cli >=0.2.1)", () => {
  for (const t of tools) {
    const schema = t.input_schema as any;
    assert.ok(schema.properties.intent, `${t.name} missing intent property`);
    assert.ok((schema.required as string[]).includes("intent"), `${t.name} must require intent`);
  }
});

test("formatIntent privacy default withholds the verbatim line", () => {
  const out = formatIntent("Help the user order dinner");
  assert.match(out, /^Summary: Help the user order dinner\n/);
  assert.match(out, /user prompt\/purpose: "\(not shared/);
});

test("formatIntent passes through a model-authored verbatim format", () => {
  const full = 'Summary: Help the user order lunch\nuser prompt/purpose: "get me tacos"';
  assert.equal(formatIntent(full), full);
});

test("formatIntent falls back when the model omits intent", () => {
  assert.match(formatIntent(null), /^Summary: Operate the Peckish/);
  assert.match(formatIntent("  "), /^Summary: Operate the Peckish/);
});

test("required fields survive strictification", () => {
  const addItems = tools.find((t) => t.name === "add_items_to_cart")!;
  const schema = addItems.input_schema as any;
  assert.deepEqual(schema.required, ["store_id", "menu_id", "items", "intent"]);
  const itemSchema = schema.properties.items.items;
  assert.deepEqual(itemSchema.required, ["item_id", "item_name", "quantity"]);
  assert.equal(itemSchema.additionalProperties, false);
  // nested_options is explicitly two-level (no freeform objects allowed under strict)
  const optSchema = itemSchema.properties.nested_options.items;
  assert.equal(optSchema.additionalProperties, false);
  assert.equal(optSchema.properties.options.items.additionalProperties, false);
});

// ---------------------------------------------------------------------------
// tools: menu trimming
// ---------------------------------------------------------------------------

test("trimMenuItem keeps ordering signal, drops noise, truncates descriptions", () => {
  const item = trimMenuItem({
    item_id: "i_123",
    name: "Bulgogi Bowl",
    description: "x".repeat(500),
    price: 16.95,
    price_varies: false,
    category_name: "Bowls",
    has_required_modifiers: true,
    is_orderable: true,
  });
  assert.equal(item.item_id, "i_123");
  assert.equal((item as any).has_required_modifiers, true);
  assert.ok((item.description as string).length <= 161);
  assert.equal((item as any).is_orderable, undefined, "orderable items carry no flag");
  assert.equal((item as any).price_varies, undefined, "false price_varies is dropped");
});

test("trimMenuItem surfaces unavailability", () => {
  const item = trimMenuItem({ item_id: "i_1", name: "X", is_orderable: false, unavailability_reason: "store_closed" });
  assert.equal((item as any).is_orderable, false);
  assert.equal((item as any).unavailability_reason, "store_closed");
});

// ---------------------------------------------------------------------------
// costs
// ---------------------------------------------------------------------------

test("addUsage tolerates null fields from the API", () => {
  const total = addUsage(EMPTY_USAGE, {
    input_tokens: 100,
    output_tokens: 50,
    cache_read_input_tokens: null,
    cache_creation_input_tokens: null,
  });
  assert.equal(total.input_tokens, 100);
  assert.equal(total.cache_read_input_tokens, 0);
});

test("estimateCostUsd prices sonnet-5 correctly incl. cache rates", () => {
  const usd = estimateCostUsd("claude-sonnet-5", {
    input_tokens: 1_000_000,       // $3
    output_tokens: 1_000_000,      // $15
    cache_read_input_tokens: 1_000_000,     // $0.30
    cache_creation_input_tokens: 1_000_000, // $3.75
  });
  assert.ok(Math.abs(usd - 22.05) < 0.001, `got ${usd}`);
});

test("formatCost floors tiny amounts", () => {
  assert.equal(formatCost(0.001), "<$0.01");
  assert.equal(formatCost(0.12), "~$0.12");
});

// ---------------------------------------------------------------------------
// platform: dd-cli version detection (gates the >=0.2.3 features)
// ---------------------------------------------------------------------------

test("parseVersion reads the version out of whatever --version prints", () => {
  assert.equal(parseVersion("dd-cli 0.2.5"), "0.2.5");
  assert.equal(parseVersion("dd-cli version v0.2.5 (darwin-arm64)"), "0.2.5");
  assert.equal(parseVersion("0.2.5\n"), "0.2.5");
  assert.equal(parseVersion("dd-cli/0.2.5-rc1"), "0.2.5");
  assert.equal(parseVersion("no version here"), null);
});

test("compareVersions orders releases numerically, not lexically", () => {
  assert.ok(compareVersions("0.2.5", "0.2.4") > 0);
  assert.ok(compareVersions("0.2.10", "0.2.9") > 0, "10 > 9, not '1' < '9'");
  assert.equal(compareVersions("0.2.5", "0.2.5"), 0);
  assert.ok(compareVersions("0.2.2", "0.2.5") < 0);
  assert.ok(compareVersions("0.3", "0.2.9") > 0, "missing components count as 0");
});

test("ddCliVersionLine names exactly the features an old binary is missing", () => {
  assert.equal(ddCliVersionLine(DD_CLI_RECOMMENDED_VERSION), DD_CLI_RECOMMENDED_VERSION);
  assert.equal(ddCliVersionLine("0.3.0"), "0.3.0", "a newer binary needs no caveat");
  assert.equal(ddCliVersionLine(null), "unknown");

  const old = ddCliVersionLine("0.2.2");
  assert.match(old, /find_address/);
  assert.match(old, /promo-aware menus/);
  assert.match(old, /search filters/);

  const mid = ddCliVersionLine("0.2.4");
  assert.doesNotMatch(mid, /find_address/, "0.2.4 has address lookup");
  assert.doesNotMatch(mid, /promo-aware menus/, "0.2.4 has promo-aware menus");
  assert.match(mid, /search filters/, "but not the 0.2.5 filters");
});

// ---------------------------------------------------------------------------
// tools: carry-through of fields dd-cli added after this code was written
// ---------------------------------------------------------------------------

test("carryThrough keeps promo/schedule/weight signal and drops the rest", () => {
  const kept = carryThrough({
    promotions: [{ id: "p1" }],
    qualifying_promotion_id: "p1",
    order_ahead_available: true,
    schedule_ahead_windows: [{ start: 1 }],
    weight_unit: "lb",
    purchase_type: "MEASUREMENT",
    telemetry_blob: "x".repeat(5000),
    internal_ranking_score: 0.42,
    community_rating: 4.6,
  });
  assert.deepEqual(Object.keys(kept).sort(), [
    "order_ahead_available",
    "promotions",
    "purchase_type",
    "qualifying_promotion_id",
    "schedule_ahead_windows",
    "weight_unit",
  ]);
});

test("carriesSignal matches whole tokens, not substrings", () => {
  assert.ok(carriesSignal("qualifying_promotion_id"));
  assert.ok(carriesSignal("orderAheadAvailable") === false, "camelCase is not how dd-cli names fields");
  assert.equal(carriesSignal("community_rating"), false, "'community' contains 'unit'");
  assert.equal(carriesSignal("opportunity_id"), false, "'opportunity' contains 'unit'");
});

test("carryThrough skips explicitly-handled keys and nulls", () => {
  const out = carryThrough({ items: [1, 2, 3], promotions: null, discount_text: "20% off" }, ["items"]);
  assert.deepEqual(out, { discount_text: "20% off" });
});

test("trimMenuItem carries a promotion through the allowlist", () => {
  const item = trimMenuItem({
    item_id: "i_1",
    name: "Bowl",
    price: 12,
    promotion: { text: "20% off" },
    junk_field: "dropped",
  });
  assert.deepEqual((item as any).promotion, { text: "20% off" });
  assert.equal((item as any).junk_field, undefined);
});

// ---------------------------------------------------------------------------
// tools: the dd-cli 0.2.3-0.2.5 surface is actually exposed to the model
// ---------------------------------------------------------------------------

const toolNamed = (name: string) => {
  const t = tools.find((x) => x.name === name);
  assert.ok(t, `tool ${name} is missing`);
  return t!;
};
const propsOf = (name: string) =>
  (toolNamed(name).input_schema.properties ?? {}) as Record<string, any>;

test("address lookup tools exist and add_address is treated as a mutation", () => {
  assert.ok(propsOf("find_address").query);
  const add = propsOf("add_address");
  assert.ok(add.place_id);
  assert.ok(add.printable_address, "the confirmation prompt needs something readable to show");
  assert.match(toolNamed("add_address").description!, /default/i);
});

test("search exposes the 0.2.5 filters and the 0.2.4 address_id", () => {
  const p = propsOf("search_restaurants");
  assert.ok(p.address_id);
  assert.ok(p.dashpass_only);
  assert.equal(p.price_tier.type, "array");
  assert.deepEqual(p.distance_preference.enum, ["nearby", "balanced", "broad"]);
  assert.ok(p.max_eta_minutes);
});

test("menu and item details can be priced against a chosen address", () => {
  assert.ok(propsOf("get_menu").address_id);
  assert.ok(propsOf("get_restaurant_item_details").address_id);
});

test("cart adds can express weight-priced items and exact modifications", () => {
  const item = (propsOf("add_items_to_cart").items.items.properties ?? {}) as Record<string, any>;
  assert.ok(item.unit);
  assert.deepEqual(item.default_handling.enum, ["default", "exact"]);
  assert.match(item.quantity.description, /decimal/i);
});

test("order history can include group orders", () => {
  assert.ok(propsOf("get_order_history").include_group_order);
});

// ---------------------------------------------------------------------------
// guests: the key the store matches on, and the token-finder
// ---------------------------------------------------------------------------

test("guestKey normalizes case and spacing so one person stays one guest", () => {
  assert.equal(guestKey("Luke", "Wulf"), "luke wulf");
  assert.equal(guestKey("  luke ", " WULF  "), "luke wulf");
  assert.equal(guestKey("Luke", "Wulf"), guestKey("LUKE", "wulf"));
  assert.notEqual(guestKey("Luke", "Wulf"), guestKey("Luke", "Wolf"));
});

test("guestKey tolerates a missing half without colliding with another name", () => {
  assert.equal(guestKey("Prince", ""), "prince");
  assert.notEqual(guestKey("Prince", ""), guestKey("", "Prince2"));
});

test("findGuestToken digs the one-time token out of wherever it is nested", () => {
  assert.equal(findGuestToken({ guest_token: "t1" }), "t1");
  assert.equal(findGuestToken({ cart: { sub: { guest_token: "t2" } } }), "t2");
  assert.equal(findGuestToken({ carts: [{ guest_token: "t3" }] }), "t3");
  assert.equal(findGuestToken({ cart_uuid: "c1" }), null);
  assert.equal(findGuestToken({ guest_token: "" }), null, "empty is not a token");
  assert.equal(findGuestToken(null), null);
});

test("stripUiFields removes guest_token at any depth", () => {
  const cleaned = stripUiFields({
    cart_uuid: "c1",
    guest_cart: { name: "Luke Wulf", guest_token: "gtok_secret" },
    list: [{ guest_token: "gtok_other" }],
  });
  const text = JSON.stringify(cleaned);
  assert.ok(!text.includes("gtok_secret"));
  assert.ok(!text.includes("gtok_other"));
  assert.ok(text.includes("Luke Wulf"), "the guest's name is not the secret");
});

test("guest sub-cart params are exposed on the cart tool, tokens are not", () => {
  const add = tools.find((t) => t.name === "add_items_to_cart")!;
  const props = add.input_schema.properties as Record<string, any>;
  assert.ok(props.guest_first_name);
  assert.ok(props.guest_last_name);
  assert.ok(props.group_cart_url);
  assert.ok(
    !JSON.stringify(add.input_schema).includes("guest_token"),
    "the model must have no way to supply or receive a token",
  );
  assert.ok(tools.some((t) => t.name === "list_cart_guests"));
});

// ---------------------------------------------------------------------------
// order status lifecycle — shape confirmed live against dd-cli 0.2.5
// ---------------------------------------------------------------------------

test("classifyOrderStatus reads result.status, never a top-level status", () => {
  // The flat shape is what Peckish wrongly assumed; it must not be honoured.
  assert.equal(classifyOrderStatus({ status: "completed" }).not_found, true);
  assert.equal(classifyOrderStatus({ result: { status: "completed" } }).status, "completed");
});

test("classifyOrderStatus keeps polling while processing or mid-delivery", () => {
  for (const status of ["pending", "store_confirmed", "dasher_assigned", "dasher_nearby"]) {
    const c = classifyOrderStatus({ result: { status } });
    assert.equal(c.keep_polling, true, `${status} should keep polling`);
    assert.equal(c.is_terminal, false, `${status} is not terminal`);
  }
});

test("classifyOrderStatus treats placed and later stages as created", () => {
  for (const status of ["placed", "store_confirmed", "picked_up", "completed"]) {
    assert.equal(classifyOrderStatus({ result: { status } }).order_created, true, status);
  }
});

test("classifyOrderStatus stops at every terminal status", () => {
  for (const status of ["completed", "cancelled", "action_required", "order_declined"]) {
    const c = classifyOrderStatus({ result: { status } });
    assert.equal(c.is_terminal, true, `${status} should be terminal`);
    assert.equal(c.keep_polling, false, `${status} should stop the poll`);
  }
});

test("classifyOrderStatus does not call a cancelled order created", () => {
  const c = classifyOrderStatus({ result: { status: "cancelled" } });
  assert.equal(c.order_created, false);
  assert.equal(c.is_terminal, true);
});

test("classifyOrderStatus rejects the vocabulary 0.2.3 removed", () => {
  for (const status of ["successful", "failed"]) {
    assert.equal(classifyOrderStatus({ result: { status } }).order_created, false, status);
  }
});

test("classifyOrderStatus reports a missing status as not_found and terminal", () => {
  for (const payload of [{}, null, undefined, { result: {} }, { result: { status: "" } }]) {
    const c = classifyOrderStatus(payload as any);
    assert.equal(c.not_found, true);
    assert.equal(c.is_terminal, true);
    assert.equal(c.keep_polling, false);
  }
});

test("popularity keys carry through the menu trimmer", () => {
  for (const k of ["is_popular", "popularity_rank", "popular_modifications"]) {
    assert.equal(carriesSignal(k), true, `${k} must reach the model`);
  }
  assert.equal(carriesSignal("popsicle_id"), false, "substring matches must not qualify");
});
