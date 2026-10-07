#!/usr/bin/env node
/**
 * A stand-in for the real dd-cli binary, so the tool layer can be exercised
 * end-to-end without a DoorDash account.
 *
 * It cannot tell us what dd-cli's real flags are — only DoorDash's binary can
 * do that. What it does prove is the half Peckish owns: that the handlers
 * build the argv they claim to, that version gating actually gates, and that
 * the response trimmers keep what they promise to keep.
 *
 * Driven by two environment variables:
 *   FAKE_DD_CLI_LOG      file to append each invocation's argv to, as JSON lines
 *   FAKE_DD_CLI_VERSION  what `--version` reports (empty => exit non-zero, as
 *                        a binary too old to have the flag would)
 */
import { appendFileSync } from "node:fs";

const argv = process.argv.slice(2);

if (process.env.FAKE_DD_CLI_LOG) {
  appendFileSync(process.env.FAKE_DD_CLI_LOG, JSON.stringify(argv) + "\n");
}

if (argv.includes("--version")) {
  const version = process.env.FAKE_DD_CLI_VERSION ?? "";
  if (!version) {
    process.stderr.write("unknown flag: --version\n");
    process.exit(2);
  }
  process.stdout.write(`dd-cli ${version}\n`);
  process.exit(0);
}

/** Value of a flag in the recorded argv, or undefined. */
const flag = (name) => {
  const i = argv.indexOf(name);
  return i === -1 ? undefined : argv[i + 1];
};

// The command is the first non-flag token(s): "search", "cart add-items", …
// `--json-output` leads the argv, so it is skipped rather than terminating.
const words = [];
for (const a of argv) {
  if (a === "--json-output") continue;
  if (a.startsWith("-")) break;
  words.push(a);
}
const command = words.join(" ");

/** dd-cli answers in an MCP envelope; Peckish reads structuredContent. */
const reply = (structuredContent) => {
  process.stdout.write(JSON.stringify({ content: [], structuredContent, isError: false }));
  process.exit(0);
};

/** The one value every containment test hunts for. */
const GUEST_TOKEN = "gtok_secret_abc123";

const RESPONSES = {
  "address list": () => ({
    addresses: [
      {
        address_id: "addr_default",
        printable_address: "500 Main St, Springfield",
        label: "Home",
        lat: 37.77,
        lng: -122.42,
        is_default: true,
      },
      {
        address_id: "addr_work",
        printable_address: "1 Office Plaza, Springfield",
        label: "Work",
        lat: 37.79,
        lng: -122.4,
        is_default: false,
      },
    ],
  }),

  "address find": () => ({
    candidates: [
      { place_id: "place_abc", printable_address: "742 Evergreen Terrace, Springfield" },
    ],
  }),

  "address add": () => ({ success: true, address_id: "addr_new", is_default: true }),

  search: () => ({
    stores: [
      {
        store_id: "store_1",
        name: "Ramen House",
        distance: "0.4 mi",
        delivery_time: "25 min",
        rating: 4.7,
        review_count: 1200,
        // dd-cli >=0.2.5 pickup availability
        offers_pickup: true,
        asap_pickup_availability: "available",
        scheduled_pickup_availability: "available",
        next_open_time_asap_pickup_ms: 1790000000000,
        // dd-cli >=0.2.5 order-ahead
        order_ahead_available: true,
        // noise the trimmer should still drop
        internal_ranking_score: 0.91,
        community_rating: 4.2,
      },
    ],
  }),

  menu: () => ({
    store_id: "store_1",
    store_name: "Ramen House",
    menu_id: "menu_1",
    store_is_open: true,
    // Shapes below match dd-cli 0.2.5's `menu --help`, which names these
    // fields: promotions[] carries title/description/code, items reference
    // them by code through applicable_promotion_ids.
    store_next_open_time: 1790000000000,
    promotions: [{ title: "20% off $25+", description: "Spend $25, save 20%", code: "SAVE20" }],
    supports_order_ahead: true,
    internal_experiment_bucket: "b7",
    items: [
      {
        item_id: "i_100",
        name: "Tonkotsu Ramen",
        description: "Pork broth, chashu, egg",
        price: 1695,
        category_name: "Ramen",
        has_required_modifiers: true,
        is_orderable: true,
        applicable_promotion_ids: ["SAVE20"],
        orderability: ["asap", "schedule_ahead"],
        is_popular: true,
        popularity_rank: 2,
        popular_modifications: ["extra chashu"],
        telemetry_blob: "x".repeat(400),
      },
      {
        item_id: "i_200",
        name: "Sliced Pork Belly",
        description: "Sold by weight",
        price: 899,
        price_varies: true,
        category_name: "Butcher",
        is_orderable: true,
        weight_unit: "lb",
        purchase_type: "MEASUREMENT",
      },
    ],
  }),

  "restaurant-item-details": () => ({
    item_id: "100",
    name: "Tonkotsu Ramen",
    applicable_promotion_ids: ["SAVE20"],
    orderability: ["asap"],
    extras: [],
  }),

  "cart add-items": (flag) => {
    const base = process.env.FAKE_DD_CLI_NO_CART_UUID
      ? { success: true }
      : { cart_uuid: "cart_1", success: true, order_ahead_available: true };
    const guest = flag("--guest-json");
    if (!guest) return base;
    const parsed = JSON.parse(guest);
    if (!parsed.first_name) return { ...base, guest_cart: { acted_for: "existing guest" } };

    // dd-cli returns the one-time guest_token only on a new guest's first add,
    // nested on the sub-cart it just created. FAKE_DD_CLI_GUEST_SCENARIO makes
    // it return that credential in shapes Peckish does not expect, so the
    // containment guarantee can be attacked rather than assumed.
    const name = `${parsed.first_name} ${parsed.last_name}`;
    switch (process.env.FAKE_DD_CLI_GUEST_SCENARIO) {
      case "camel":
        // A camelCase spelling: neither the finder nor the stripper matches it.
        return { ...base, guest_cart: { name, guestToken: GUEST_TOKEN } };
      case "in_message":
        // Correctly keyed, but also echoed inside a free-text field.
        return {
          ...base,
          message: `Created sub-cart for ${name} (token ${GUEST_TOKEN})`,
          guest_cart: { name, guest_token: GUEST_TOKEN },
        };
      case "deep": {
        // Nested past findGuestToken's depth cap.
        let node = { guest_token: GUEST_TOKEN };
        for (let i = 0; i < 10; i++) node = { wrap: node };
        return { ...base, guest_cart: { name, ...node } };
      }
      case "deep_camel": {
        // Both evasions at once: a camelCase spelling nested past the finder's
        // depth cap. Nothing can learn the value, so redaction has nothing to
        // work with — the stripper's key normalization is the only defence.
        let node = { guestToken: GUEST_TOKEN };
        for (let i = 0; i < 10; i++) node = { wrap: node };
        return { ...base, guest_cart: { name, ...node } };
      }
      case "array":
        return { ...base, guest_carts: [{ name, guest_token: GUEST_TOKEN }] };
      case "error_echo":
        // Non-zero exit with the credential in stdout — this is what lands in
        // DdCliError.detail, which never passed through the stripper.
        process.stdout.write(
          JSON.stringify({
            content: [],
            structuredContent: { guest_cart: { name, guest_token: GUEST_TOKEN } },
            isError: true,
          }),
        );
        process.stderr.write(`partial failure for ${name}; guest_token=${GUEST_TOKEN}\n`);
        process.exit(1);
        break;
      default:
        return { ...base, guest_cart: { name, guest_token: GUEST_TOKEN } };
    }
  },

  "cart list": () => ({ carts: [] }),

  "cart delete": () => ({ success: true }),

  "order history": () => ({
    orders: [
      {
        order_uuid: "order_1",
        store_id: "store_1",
        store_name: "Ramen House",
        // Real 0.2.5 rows are dated with order_date / order_fulfilled_at (ISO
        // strings) and carry NO total and no per-item price.
        order_date: "2026-08-26T23:39:31.029Z",
        order_fulfilled_at: "2026-08-26T23:57:15.541Z",
        items: [{ item_id: "37275430436", name: "Tonkotsu Ramen", quantity: 1 }],
        is_reorderable: true,
        fulfillment_type: "FULFILLMENT_TYPE_DX_DELIVERY",
        // dd-cli >=0.2.3 group-order participation
        is_group_order: true,
        group_order_role: "HOST",
      },
    ],
    page_full: false,
  }),

  // Real 0.2.5 shape: everything about the order sits under `result`; there is
  // no top-level `status`, and `successful` is not a value it can return.
  "order status": () => ({
    result: {
      status: "completed",
      status_message: null,
      status_updated_at: "2026-08-26T23:57:15.541Z",
      action_required: false,
      merchant_name: "Ramen House",
      is_pickup: false,
      quoted_delivery_time: "2026-08-27T00:12:32Z",
      actual_delivery_time: "2026-08-26T23:57:15.541Z",
      eta_trend: null,
      late_reason: null,
      cancellation_reason: null,
    },
    success: true,
    message: "Order Complete",
  }),

  "order submit": () => ({ order_uuid: "order_1", success: true }),

  "find-nearby-stores": () => ({ stores: [] }),
};

const handler = RESPONSES[command];
if (!handler) {
  process.stderr.write(`fake dd-cli: no canned response for "${command}"\n`);
  process.exit(3);
}
reply(handler(flag));
