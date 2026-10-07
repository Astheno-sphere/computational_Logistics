/**
 * End-to-end tests for the tool handlers against a fake dd-cli.
 *
 * The unit tests cover pure functions; these cover the part that actually
 * broke things historically — the argv Peckish builds, and what survives the
 * response trimmers. A fake binary can't tell us dd-cli's real flag names
 * (see tests/fixtures/fake-dd-cli.mjs), but it proves Peckish sends what it
 * says it sends, and that the version gate really gates.
 *
 * DD_CLI_PATH is read when ddcli.ts is first imported, so every import here
 * is dynamic and happens after the environment is set up.
 */
import { test, before, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { chmodSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const FAKE = fileURLToPath(new URL("./fixtures/fake-dd-cli.mjs", import.meta.url));
const workdir = mkdtempSync(join(tmpdir(), "peckish-it-"));
const LOG = join(workdir, "argv.log");

process.env.DD_CLI_PATH = FAKE;
process.env.FAKE_DD_CLI_LOG = LOG;
process.env.FAKE_DD_CLI_VERSION = "0.2.5";
// The guest store, preferences and audit log all hang off the home directory.
// Point it at the temp workdir before anything imports them.
process.env.HOME = workdir;

type Tools = typeof import("../src/tools.js");
type DdCli = typeof import("../src/ddcli.js");
type Guests = typeof import("../src/guests.js");
let tools: Tools;
let ddcli: DdCli;
let guests: Guests;

before(async () => {
  chmodSync(FAKE, 0o755);
  tools = await import("../src/tools.js");
  ddcli = await import("../src/ddcli.js");
  guests = await import("../src/guests.js");
});

process.on("exit", () => rmSync(workdir, { recursive: true, force: true }));

/** Reset recorded argv and every per-process cache between cases. */
function reset(version = "0.2.5") {
  writeFileSync(LOG, "");
  process.env.FAKE_DD_CLI_VERSION = version;
  ddcli.resetVersionCache();
  ddcli.invalidateDefaultAddress();
  ddcli.setCallIntent("Help the user order dinner");
}

beforeEach(() => reset());

/** Every invocation the fake recorded, oldest first. */
const calls = (): string[][] =>
  readFileSync(LOG, "utf8")
    .split("\n")
    .filter(Boolean)
    .map((l) => JSON.parse(l));

/**
 * The command words of an invocation — argv leads with `--json-output`, and
 * flag values (`--query "742 Evergreen"`) must not be mistaken for them.
 */
function commandOf(argv: string[]): string[] {
  const words: string[] = [];
  for (const a of argv) {
    if (a === "--json-output") continue;
    if (a.startsWith("-")) break;
    words.push(a);
  }
  return words;
}

const invocations = (...words: string[]): string[][] =>
  calls().filter((argv) => words.every((w, i) => commandOf(argv)[i] === w));

/** The first recorded invocation whose command words start with `words`. */
function callFor(...words: string[]): string[] {
  const [hit] = invocations(...words);
  assert.ok(hit, `no dd-cli call for "${words.join(" ")}" — saw ${JSON.stringify(calls())}`);
  return hit;
}

const valueOf = (argv: string[], flag: string) => argv[argv.indexOf(flag) + 1];
const run = async (tool: string, input: Record<string, unknown> = {}) =>
  JSON.parse(await tools.toolHandlers[tool](input));

// ---------------------------------------------------------------------------
// Location: --address-id (dd-cli >=0.2.4) vs --lat/--lng
// ---------------------------------------------------------------------------

test("search prefers the saved address id on a 0.2.4+ binary", async () => {
  const res = await run("search_restaurants", { query: "ramen" });
  const argv = callFor("search");
  assert.equal(valueOf(argv, "--address-id"), "addr_default");
  assert.ok(!argv.includes("--lat"), "address-id and lat/lng are mutually exclusive");
  assert.equal(res.searched_near, "default saved address");
});

test("search falls back to coordinates on a pre-0.2.4 binary", async () => {
  reset("0.2.2");
  await run("search_restaurants", { query: "ramen" });
  const argv = callFor("search");
  assert.ok(!argv.includes("--address-id"), "0.2.2 has no --address-id to give");
  assert.equal(valueOf(argv, "--lat"), "37.77");
  assert.equal(valueOf(argv, "--lng"), "-122.42");
});

test("an explicit address_id wins and skips the address lookup", async () => {
  await run("search_restaurants", { query: "ramen", address_id: "addr_work" });
  assert.equal(valueOf(callFor("search"), "--address-id"), "addr_work");
  assert.equal(
    invocations("address", "list").length,
    0,
    "no need to read the default address when one was named",
  );
});

test("explicit coordinates are passed through without an address id", async () => {
  await run("search_restaurants", { query: "ramen", lat: 40.7, lng: -74 });
  const argv = callFor("search");
  assert.equal(valueOf(argv, "--lat"), "40.7");
  assert.ok(!argv.includes("--address-id"));
});

test("menus and item details are priced against an address on 0.2.5", async () => {
  await run("get_menu", { store_id: "store_1" });
  assert.equal(valueOf(callFor("menu"), "--address-id"), "addr_default");

  reset();
  await run("get_restaurant_item_details", {
    store_id: "store_1",
    menu_id: "menu_1",
    item_id: "i_100",
  });
  assert.equal(valueOf(callFor("restaurant-item-details"), "--address-id"), "addr_default");
});

test("menus carry no address flag on a pre-0.2.4 binary", async () => {
  reset("0.2.2");
  await run("get_menu", { store_id: "store_1" });
  const argv = callFor("menu");
  assert.ok(!argv.includes("--address-id"));
  assert.equal(
    invocations("address", "list").length,
    0,
    "and it does not pay for an address lookup it cannot use",
  );
});

// ---------------------------------------------------------------------------
// dd-cli 0.2.5 search filters
// ---------------------------------------------------------------------------

test("search filters reach the command line, price tiers repeating", async () => {
  await run("search_restaurants", {
    query: "ramen",
    dashpass_only: true,
    price_tier: [1, 2],
    distance_preference: "nearby",
    max_eta_minutes: 30,
  });
  const argv = callFor("search");
  assert.ok(argv.includes("--dashpass-only"));
  assert.deepEqual(
    argv.filter((a, i) => argv[i - 1] === "--price-tier"),
    ["1", "2"],
    "--price-tier repeats, one flag per tier",
  );
  assert.equal(valueOf(argv, "--distance-preference"), "nearby");
  assert.equal(valueOf(argv, "--max-eta-minutes"), "30");
});

test("filters are omitted entirely when unused", async () => {
  await run("search_restaurants", { query: "ramen" });
  const argv = callFor("search");
  for (const f of ["--dashpass-only", "--price-tier", "--distance-preference", "--max-eta-minutes"])
    assert.ok(!argv.includes(f), `${f} should not appear unasked`);
});

// ---------------------------------------------------------------------------
// What survives the trimmers
// ---------------------------------------------------------------------------

test("search results keep pickup availability and drop ranking noise", async () => {
  const res = await run("search_restaurants", { query: "ramen" });
  const store = res.stores[0];
  assert.equal(store.offers_pickup, true);
  assert.equal(store.asap_pickup_availability, "available");
  assert.equal(store.scheduled_pickup_availability, "available");
  assert.equal(store.next_open_time_asap_pickup_ms, 1790000000000);
  assert.equal(store.order_ahead_available, true);
  assert.equal(store.internal_ranking_score, undefined);
  assert.equal(store.community_rating, undefined, "'community' contains 'unit' but is not signal");
});

test("menus keep store promotions, item promos and weight units", async () => {
  const res = await run("get_menu", { store_id: "store_1" });
  assert.deepEqual(res.promotions, [
    { title: "20% off $25+", description: "Spend $25, save 20%", code: "SAVE20" },
  ]);
  assert.equal(res.supports_order_ahead, true, "order-ahead flag reaches the model");
  assert.equal(res.store_next_open_time, 1790000000000, "next opening time reaches the model");
  assert.equal(res.internal_experiment_bucket, undefined, "but internals do not");

  const [ramen, pork] = res.items;
  assert.deepEqual(ramen.applicable_promotion_ids, ["SAVE20"]);
  assert.deepEqual(ramen.orderability, ["asap", "schedule_ahead"], "get_menu's description promises this");
  assert.equal(ramen.telemetry_blob, undefined);
  assert.equal(pork.weight_unit, "lb");
  assert.equal(pork.purchase_type, "MEASUREMENT");
  assert.equal(pork.price_varies, true);
});

// ---------------------------------------------------------------------------
// dd-cli 0.2.3: address lookup, group orders
// ---------------------------------------------------------------------------

test("find_address calls the CLI on 0.2.3+", async () => {
  reset("0.2.3");
  const res = await run("find_address", { query: "742 Evergreen Terrace" });
  assert.equal(valueOf(callFor("address", "find"), "--query"), "742 Evergreen Terrace");
  assert.equal(res.candidates[0].place_id, "place_abc");
});

test("find_address refuses without calling a binary that lacks the command", async () => {
  reset("0.2.2");
  const res = await run("find_address", { query: "742 Evergreen Terrace" });
  assert.equal(res.unsupported, true);
  assert.match(res.note, /0\.2\.3/);
  assert.equal(
    invocations("address", "find").length,
    0,
    "an unsupported command is never attempted",
  );
});

test("order history asks for group orders and keeps their fields", async () => {
  const res = await run("get_order_history", { include_group_order: true, max: 10 });
  assert.ok(callFor("order", "history").includes("--include-group-order"));
  assert.equal(res.orders[0].is_group_order, true);
  assert.equal(res.orders[0].group_order_role, "HOST");
});

test("order history rows carry the real date fields and item ids", async () => {
  const res = await run("get_order_history", {});
  const row = res.orders[0];
  // Regression: the mapper read `created_at`, which dd-cli never returns, so
  // every row came back undated.
  assert.equal(row.order_date, "2026-08-26T23:39:31.029Z");
  assert.equal(row.order_fulfilled_at, "2026-08-26T23:57:15.541Z");
  assert.equal(row.created_at, undefined, "created_at is not a dd-cli field");
  assert.equal(row.items[0].item_id, "37275430436", "item_id was being dropped");
});

test("submit_order learns the outcome from result.status", async () => {
  const confirm = await import("../src/confirm.js");
  confirm.setConfirmationProviders({ order: async () => true, action: async () => true });
  const res = await run("submit_order", {
    cart_uuid: "cart_1",
    tip_cents: 500,
    confirmation_summary: "1x Tonkotsu Ramen, $22.10 total, $5 tip",
  });
  // Regression: the poll read `finalStatus.status`, which never exists, so it
  // burned all 8 attempts and reported nothing the model could act on.
  assert.equal(res.final_status.result.status, "completed");
  assert.equal(res.lifecycle.order_created, true);
  assert.equal(res.lifecycle.keep_polling, false);
  assert.match(res.note, /lifecycle\.order_created/, "the note must point at the derived flag");
  assert.match(res.note, /result\.status/, "and at where the status really lives");
});

test("order status is read from result.status, not the top level", async () => {
  const res = await run("get_order_status", { order_uuid: "order_1" });
  // The payload nests under `result`; a top-level `status` never exists.
  assert.equal(res.status, undefined);
  assert.equal(res.result.status, "completed");
  assert.equal(res.lifecycle.status, "completed");
  assert.equal(res.lifecycle.order_created, true);
  assert.equal(res.lifecycle.is_terminal, true);
  assert.equal(res.lifecycle.keep_polling, false);
  // The fields the tool description promises must survive the passthrough.
  assert.ok("eta_trend" in res.result);
  assert.ok("late_reason" in res.result);
  assert.ok("cancellation_reason" in res.result);
  assert.equal(res.result.actual_delivery_time, "2026-08-26T23:57:15.541Z");
});

test("menu items carry popularity, which Peckish used to deny existed", async () => {
  const res = await run("get_menu", { store_id: "store_1" });
  const ramen = res.items[0];
  assert.equal(ramen.is_popular, true);
  assert.equal(ramen.popularity_rank, 2);
  assert.deepEqual(ramen.popular_modifications, ["extra chashu"]);
});

test("order history omits the flag by default", async () => {
  await run("get_order_history", {});
  assert.ok(!callFor("order", "history").includes("--include-group-order"));
});

// ---------------------------------------------------------------------------
// dd-cli 0.2.5: weight-priced items and merchant defaults
// ---------------------------------------------------------------------------

test("cart adds serialize decimal weights, units and default_handling", async () => {
  await run("add_items_to_cart", {
    store_id: "store_1",
    menu_id: "menu_1",
    items: [
      { item_id: "i_200", item_name: "Sliced Pork Belly", quantity: 0.5, unit: "lb" },
      { item_id: "i_100", item_name: "Tonkotsu Ramen", quantity: 1, default_handling: "exact" },
    ],
  });
  const sent = JSON.parse(valueOf(callFor("cart", "add-items"), "--items-json"));
  assert.equal(sent[0].quantity, 0.5, "decimal weight survives serialization");
  assert.equal(sent[0].unit, "lb");
  assert.equal(sent[1].default_handling, "exact");
  assert.equal(sent[1].item_id, "100", "the i_ prefix is still stripped");
});

// ---------------------------------------------------------------------------
// Cross-cutting invariants
// ---------------------------------------------------------------------------

test("every consumer command still carries --json-output and --intent", async () => {
  await run("search_restaurants", { query: "ramen" });
  await run("get_menu", { store_id: "store_1" });
  reset("0.2.3");
  await run("find_address", { query: "x" });
  await run("get_order_history", {});

  for (const argv of calls()) {
    if (argv.includes("--version")) continue;
    assert.equal(argv[0], "--json-output", `missing --json-output: ${argv.join(" ")}`);
    assert.ok(argv.includes("--intent"), `missing --intent: ${argv.join(" ")}`);
  }
});

test("the intent sent to DoorDash withholds the user's verbatim words", async () => {
  ddcli.setCallIntent("Help the user order dinner");
  await run("search_restaurants", { query: "ramen" });
  const intent = valueOf(callFor("search"), "--intent");
  assert.match(intent, /^Summary: Help the user order dinner/);
  assert.match(intent, /not shared/, "the verbatim line is withheld by default");
});

test("the version is probed once per process, not once per call", async () => {
  await run("search_restaurants", { query: "ramen" });
  await run("get_menu", { store_id: "store_1" });
  await run("get_menu", { store_id: "store_1" });
  assert.equal(
    calls().filter((a) => a.includes("--version")).length,
    1,
    "the version probe is cached",
  );
});

test("the default address is read once and refreshed when it changes", async () => {
  await run("search_restaurants", { query: "ramen" });
  await run("get_menu", { store_id: "store_1" });
  const listCalls = () => invocations("address", "list").length;
  assert.equal(listCalls(), 1, "cached across handlers");

  ddcli.invalidateDefaultAddress();
  await run("get_menu", { store_id: "store_1" });
  assert.equal(listCalls(), 2, "and re-read once invalidated");
});

// ---------------------------------------------------------------------------
// Guest sub-carts
//
// The guest_token is a bearer credential for one person's sub-cart, it is
// returned exactly once, and dd-cli's guidance is to keep it out of logs and
// away from humans. Peckish holds it; the model works in names. These tests
// are as much about the token NOT going anywhere as about the flags.
// ---------------------------------------------------------------------------

const GUEST_CART = "cart_1";
const addGuest = (first: string, last: string, cart: string | null = GUEST_CART) =>
  run("add_items_to_cart", {
    store_id: "store_1",
    menu_id: "menu_1",
    items: [{ item_id: "i_100", item_name: "Tonkotsu Ramen", quantity: 1 }],
    ...(cart ? { cart_uuid: cart } : {}),
    guest_first_name: first,
    guest_last_name: last,
  });

test("a new guest is introduced by name, and the token never comes back", async () => {
  guests.forgetCart(GUEST_CART);
  const res = await addGuest("Luke", "Wulf");

  const sent = JSON.parse(valueOf(callFor("cart", "add-items"), "--guest-json"));
  assert.deepEqual(sent, { first_name: "Luke", last_name: "Wulf" });
  assert.equal(res.guest_add, "new guest");

  const serialized = JSON.stringify(res);
  assert.ok(!serialized.includes("gtok_secret_abc123"), "the token must not reach the model");
  assert.ok(!serialized.includes("guest_token"), "not even the key");
});

test("the token is stored and replaces the name on every later add", async () => {
  guests.forgetCart(GUEST_CART);
  await addGuest("Luke", "Wulf");
  assert.equal(guests.guestToken(GUEST_CART, "Luke", "Wulf"), "gtok_secret_abc123");

  reset();
  const res = await addGuest("Luke", "Wulf");
  const sent = JSON.parse(valueOf(callFor("cart", "add-items"), "--guest-json"));
  assert.deepEqual(sent, { guest_token: "gtok_secret_abc123" });
  assert.equal(sent.first_name, undefined, "a token must not be sent alongside a name");
  assert.equal(res.guest_add, "existing guest");
});

test("the same guest is recognised regardless of case and spacing", async () => {
  guests.forgetCart(GUEST_CART);
  await addGuest("Luke", "Wulf");
  reset();
  await addGuest("  luke  ", "WULF");
  const sent = JSON.parse(valueOf(callFor("cart", "add-items"), "--guest-json"));
  assert.deepEqual(sent, { guest_token: "gtok_secret_abc123" }, "not treated as a second guest");
});

test("a guest add with no cart to join is refused before dd-cli is called", async () => {
  const res = await addGuest("Ada", "Lovelace", null);
  assert.equal(res.success, false);
  assert.match(res.error, /existing group cart/i);
  assert.equal(invocations("cart", "add-items").length, 0);
});

test("a guest add cannot also create a cart", async () => {
  for (const extra of [{ group_cart: true }, { spend_limit_cents: 2500 }]) {
    reset();
    const res = await run("add_items_to_cart", {
      store_id: "store_1",
      menu_id: "menu_1",
      items: [{ item_id: "i_100", item_name: "Ramen", quantity: 1 }],
      cart_uuid: GUEST_CART,
      guest_first_name: "Ada",
      guest_last_name: "Lovelace",
      ...extra,
    });
    assert.equal(res.success, false, `${JSON.stringify(extra)} should be refused`);
    assert.equal(invocations("cart", "add-items").length, 0);
  }
});

test("half a guest name is refused — the name is the tracking key", async () => {
  const res = await run("add_items_to_cart", {
    store_id: "store_1",
    menu_id: "menu_1",
    items: [{ item_id: "i_100", item_name: "Ramen", quantity: 1 }],
    cart_uuid: GUEST_CART,
    guest_first_name: "Ada",
  });
  assert.equal(res.success, false);
  assert.match(res.error, /guest_last_name/);
  assert.equal(invocations("cart", "add-items").length, 0);
});

test("a normal add is untouched by any of this", async () => {
  const res = await run("add_items_to_cart", {
    store_id: "store_1",
    menu_id: "menu_1",
    items: [{ item_id: "i_100", item_name: "Ramen", quantity: 1 }],
  });
  assert.ok(!callFor("cart", "add-items").includes("--guest-json"));
  assert.equal(res.cart_uuid, "cart_1");
});

test("joining someone's group cart uses the link, not the group-cart flag", async () => {
  await run("add_items_to_cart", {
    store_id: "store_1",
    menu_id: "menu_1",
    items: [{ item_id: "i_100", item_name: "Ramen", quantity: 1 }],
    group_cart_url: "https://drd.sh/cart/abc/",
  });
  const argv = callFor("cart", "add-items");
  assert.equal(valueOf(argv, "--group-cart-url"), "https://drd.sh/cart/abc/");
  assert.ok(!argv.includes("--group-cart"), "joining is not creating");
});

test("a guest add that cannot be recorded says so instead of reporting success", async () => {
  guests.forgetCart("cart_1");
  // Joining by link alone: the fake answers without a cart_uuid to file under.
  process.env.FAKE_DD_CLI_NO_CART_UUID = "1";
  try {
    const res = await run("add_items_to_cart", {
      store_id: "store_1",
      menu_id: "menu_1",
      items: [{ item_id: "i_100", item_name: "Ramen", quantity: 1 }],
      group_cart_url: "https://drd.sh/cart/abc/",
      guest_first_name: "Ada",
      guest_last_name: "Lovelace",
    });
    assert.match(res.warning, /second one/i, "the loss of continuity must be surfaced");
  } finally {
    delete process.env.FAKE_DD_CLI_NO_CART_UUID;
  }
});

test("list_cart_guests reports names and no tokens", async () => {
  guests.forgetCart(GUEST_CART);
  await addGuest("Luke", "Wulf");
  const res = await run("list_cart_guests", { cart_uuid: GUEST_CART });
  assert.deepEqual(res.guests, ["Luke Wulf"]);
  assert.ok(!JSON.stringify(res).includes("gtok_secret_abc123"));
});

test("deleting a cart forgets its guests", async () => {
  guests.forgetCart(GUEST_CART);
  await addGuest("Luke", "Wulf");
  assert.ok(guests.guestToken(GUEST_CART, "Luke", "Wulf"));

  await run("delete_cart", { cart_uuid: GUEST_CART });
  assert.equal(guests.guestToken(GUEST_CART, "Luke", "Wulf"), null);
});

test("the guest store is written user-only", async () => {
  guests.forgetCart(GUEST_CART);
  await addGuest("Luke", "Wulf");
  const mode = statSync(guests.guestsFilePath()).mode & 0o777;
  assert.equal(mode, 0o600, `expected 0600, got ${mode.toString(8)}`);
});

test("stripUiFields drops a guest_token anywhere it appears", () => {
  const cleaned = ddcli.stripUiFields({
    cart_uuid: "c1",
    guest_cart: { name: "Luke Wulf", guest_token: "gtok_secret_abc123" },
  });
  assert.ok(!JSON.stringify(cleaned).includes("gtok_secret_abc123"));
});
