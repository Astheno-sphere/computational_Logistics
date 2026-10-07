/**
 * Tool definitions + handlers exposed to Claude.
 *
 * Every handler shells out to dd-cli via the sanitizing wrapper and returns a
 * JSON string. The one exception to "tools just do what they're told" is
 * submit_order, which blocks on a typed human confirmation in the terminal —
 * that gate lives here in code, not in the model's judgment.
 */
import type Anthropic from "@anthropic-ai/sdk";
import {
  ddJson,
  ddBeautify,
  getDefaultAddress,
  invalidateDefaultAddress,
  ddCliAtLeast,
  ddCliVersion,
  ddJsonRaw,
  findGuestToken,
  redactGuestTokens,
  stripUiFields,
  DdCliError,
} from "./ddcli.js";
import { guestToken, rememberGuest, listGuests, forgetCart } from "./guests.js";
import { addPreference, removePreference, listPreferences } from "./prefs.js";
import { confirmOrderPlacement, confirmAction } from "./confirm.js";
import { probeSignin, launchLogin, loginInProgress, waitForSignin } from "./signin.js";
import { canBrowserSignin, signinHint, upgradeHint } from "./platform.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const trunc = (s: unknown, n: number): string | undefined =>
  typeof s === "string" ? (s.length > n ? s.slice(0, n) + "…" : s) : undefined;

function j(value: unknown): string {
  return JSON.stringify(value);
}

interface MenuItemWire {
  item_id?: string;
  name?: string;
  description?: string;
  price?: number;
  price_varies?: boolean;
  category_name?: string;
  has_modifiers?: boolean;
  has_required_modifiers?: boolean;
  is_orderable?: boolean;
  unavailability_reason?: string;
  [key: string]: unknown;
}

/**
 * Fields the trimmers keep beyond their explicit allowlist.
 *
 * dd-cli keeps adding per-item and per-store signal — promotions and
 * qualifying items (0.2.4), order-ahead/schedule-ahead windows and
 * weight-priced units (0.2.5) — under names Peckish can't enumerate ahead of a
 * release. A strict allowlist silently swallowed all of it, so anything whose
 * key names one of these concepts rides along untrimmed. Everything else is
 * still dropped: menus run to thousands of items and the context is finite.
 */
const CARRY_THROUGH_TOKENS = new Set([
  "promo",
  "promos",
  "promotion",
  "promotions",
  "discount",
  "discounts",
  "deal",
  "deals",
  "savings",
  "ahead",
  // `items[].orderability` (0.2.5) is a whole token that matches none of the
  // concept words above — verified against dd-cli 0.2.5's own `menu --help`,
  // which names it. Without this the menu trimmer dropped it while
  // get_menu's description promised the model it was there.
  "orderability",
  // Confirmed live on 0.2.5: menu items carry is_popular, popularity_rank and
  // popular_modifications. Peckish used to assert to the model that no
  // popularity data exists while dropping these three fields.
  "popular",
  "popularity",
  "weight",
  "unit",
  "units",
  "measurement",
  "purchase",
]);

/**
 * Matched on whole snake_case tokens, not substrings — "community_rating"
 * contains "unit" and would otherwise ride along as promo signal.
 */
export function carriesSignal(key: string): boolean {
  return key
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .some((token) => CARRY_THROUGH_TOKENS.has(token));
}

// ---------------------------------------------------------------------------
// Order status (dd-cli >=0.2.3; shape confirmed live against 0.2.5)
//
// The payload nests the order under `result` — {result: {status, eta_trend,
// late_reason, cancellation_reason, actual_delivery_time, ...}, success,
// message}. There is NO top-level `status`, and the pre-0.2.3 values
// `successful`/`failed` no longer exist: an order that clears processing
// reports `placed` and then moves through delivery stages to `completed`.
// ---------------------------------------------------------------------------

/** Delivery/pickup stages between `placed` and a terminal status. */
const IN_PROGRESS_STATUSES = new Set([
  "scheduled",
  "store_confirmed",
  "ready_for_pickup",
  "dasher_assigned",
  "dasher_at_store",
  "picked_up",
  "dasher_nearby",
]);

/** Nothing further changes on its own — stop polling. */
const TERMINAL_STATUSES = new Set(["action_required", "order_declined", "completed", "cancelled"]);

/**
 * The order exists and stands. `cancelled` is excluded on purpose: it was
 * placed and then cancelled, so reporting it as created would mislead.
 */
const ORDER_CREATED_STATUSES = new Set(["placed", "completed", ...IN_PROGRESS_STATUSES]);

export function classifyOrderStatus(payload: Record<string, unknown> | null | undefined) {
  const result = (payload?.result ?? null) as Record<string, unknown> | null;
  const raw = result?.status;
  const status = typeof raw === "string" ? raw.toLowerCase() : "";
  if (!status) {
    // No status at all is how dd-cli reports an unknown order UUID.
    return { status: null, order_created: false, is_terminal: true, keep_polling: false, not_found: true };
  }
  return {
    status,
    order_created: ORDER_CREATED_STATUSES.has(status),
    is_terminal: TERMINAL_STATUSES.has(status),
    keep_polling: status === "pending" || IN_PROGRESS_STATUSES.has(status),
    not_found: false,
  };
}

export function carryThrough(
  source: Record<string, unknown>,
  skip: Iterable<string> = [],
): Record<string, unknown> {
  const skipped = new Set(skip);
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(source)) {
    if (skipped.has(k) || v == null) continue;
    if (carriesSignal(k)) out[k] = v;
  }
  return out;
}

export function trimMenuItem(it: MenuItemWire) {
  return {
    item_id: it.item_id,
    name: it.name,
    description: trunc(it.description, 160),
    price: it.price,
    ...(it.price_varies ? { price_varies: true } : {}),
    category: it.category_name,
    ...(it.has_required_modifiers ? { has_required_modifiers: true } : {}),
    ...(it.is_orderable === false
      ? { is_orderable: false, unavailability_reason: it.unavailability_reason }
      : {}),
    ...carryThrough(it),
  };
}

const MENU_ITEM_CAP = 160;

// ---------------------------------------------------------------------------
// Location arguments (dd-cli >=0.2.4)
//
// `search` and `find-nearby-stores` take --address-id OR --lat/--lng, never
// both; `menu` and `restaurant-item-details` take --address-id only, and use
// it to decide which promotions the user is eligible for. Peckish prefers the
// saved address id wherever the binary supports it — coordinates alone lose
// the promo context — and falls back to the old lat/lng resolution on older
// binaries.
// ---------------------------------------------------------------------------

const ADDRESS_ID_VERSION = "0.2.4";

/** Location flags for a store-search command, plus a note on what was used. */
async function locationArgs(opts: {
  address_id?: string;
  lat?: number;
  lng?: number;
}): Promise<{ args: string[]; searched_near: string }> {
  if (opts.address_id) {
    return { args: ["--address-id", String(opts.address_id)], searched_near: "requested saved address" };
  }
  if (opts.lat != null && opts.lng != null) {
    return { args: ["--lat", String(opts.lat), "--lng", String(opts.lng)], searched_near: "provided coords" };
  }
  const def = await getDefaultAddress();
  if (!def) return { args: [], searched_near: "dd-cli default" };
  if (await ddCliAtLeast(ADDRESS_ID_VERSION)) {
    return { args: ["--address-id", def.address_id], searched_near: "default saved address" };
  }
  return {
    args: ["--lat", String(def.lat), "--lng", String(def.lng)],
    searched_near: "default saved address (coordinates — dd-cli too old for promo-aware search)",
  };
}

/** --address-id for the commands that accept nothing else (menu, item details). */
async function addressIdArgs(address_id?: string): Promise<string[]> {
  if (!(await ddCliAtLeast(ADDRESS_ID_VERSION))) return [];
  if (address_id) return ["--address-id", String(address_id)];
  const def = await getDefaultAddress();
  return def ? ["--address-id", def.address_id] : [];
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

type Handler = (input: Record<string, any>) => Promise<string>;

export const toolHandlers: Record<string, Handler> = {
  async list_addresses() {
    const res = await ddJson(["address", "list"], { retryOnce: true });
    const addresses = ((res.addresses as any[]) ?? []).map((a) => ({
      address_id: a.address_id,
      printable_address: a.printable_address,
      label: a.label,
      is_default: a.is_default,
    }));
    return j({ addresses });
  },

  async set_default_address({ address_id, printable_address }) {
    const ok = await confirmAction(
      `The agent wants to change your ACCOUNT-WIDE default delivery address to:\n  ${printable_address ?? address_id}\n(This persists across the DoorDash app/web until changed again.)`,
    );
    if (!ok) return j({ success: false, declined_by_user: true });
    const res = await ddJson(["address", "set", "--address-id", String(address_id), "--yes"]);
    invalidateDefaultAddress();
    return j(res);
  },

  async find_address({ query }) {
    if (!(await ddCliAtLeast("0.2.3"))) {
      return j({
        candidates: [],
        unsupported: true,
        note: `Address lookup needs dd-cli >= 0.2.3. ${upgradeHint(await ddCliVersion())} Until then the user must add the address in the DoorDash app, after which it shows up in list_addresses.`,
      });
    }
    const res = await ddJson(["address", "find", "--query", String(query)], { retryOnce: true });
    return j(res);
  },

  async add_address({ place_id, printable_address }) {
    // `address add` saves the address AND makes it the default delivery
    // address — the same account-wide change set_default_address gates.
    const ok = await confirmAction(
      `The agent wants to SAVE a new delivery address and make it your ACCOUNT-WIDE default:\n  ${printable_address ?? place_id}\n(This persists across the DoorDash app/web until changed again.)`,
    );
    if (!ok) return j({ success: false, declined_by_user: true });
    const res = await ddJson(["address", "add", "--place-id", String(place_id)]);
    invalidateDefaultAddress();
    return j(res);
  },

  async search_restaurants({
    query,
    lat,
    lng,
    address_id,
    limit,
    dashpass_only,
    price_tier,
    distance_preference,
    max_eta_minutes,
  }) {
    const args = ["search", "-q", String(query)];
    const location = await locationArgs({ address_id, lat, lng });
    args.push(...location.args, "--limit", String(limit ?? 8));
    // dd-cli >=0.2.5 filters. Passed through only when the model asked for
    // one, so an older binary never sees a flag it can't parse unprompted.
    if (dashpass_only) args.push("--dashpass-only");
    for (const tier of (price_tier as number[]) ?? []) args.push("--price-tier", String(tier));
    if (distance_preference) args.push("--distance-preference", String(distance_preference));
    if (max_eta_minutes != null) args.push("--max-eta-minutes", String(max_eta_minutes));

    const res = await ddJson(args, { retryOnce: true });
    const stores = ((res.stores as any[]) ?? []).map((s) => ({
      store_id: s.store_id,
      name: s.name,
      distance: s.distance,
      delivery_time: s.delivery_time,
      rating: s.rating,
      review_count: s.review_count,
      ...(String(s.is_link_out) === "True" || s.is_link_out === true
        ? { is_link_out: true }
        : {}),
      // dd-cli >=0.2.5 pickup availability, per store.
      ...(s.offers_pickup != null ? { offers_pickup: s.offers_pickup } : {}),
      ...(s.asap_pickup_availability != null
        ? { asap_pickup_availability: s.asap_pickup_availability }
        : {}),
      ...(s.scheduled_pickup_availability != null
        ? { scheduled_pickup_availability: s.scheduled_pickup_availability }
        : {}),
      ...(s.next_open_time_asap_pickup_ms != null
        ? { next_open_time_asap_pickup_ms: s.next_open_time_asap_pickup_ms }
        : {}),
      ...carryThrough(s),
    }));
    return j({ stores, searched_near: location.searched_near });
  },

  async get_menu({ store_id, filter, address_id }) {
    const res = await ddJson(
      ["menu", "--store-id", String(store_id), ...(await addressIdArgs(address_id))],
      { retryOnce: true },
    );
    let items = ((res.items as MenuItemWire[]) ?? []).map(trimMenuItem);
    const total = items.length;
    if (filter) {
      const needle = String(filter).toLowerCase();
      items = items.filter(
        (it) =>
          it.name?.toLowerCase().includes(needle) ||
          it.description?.toLowerCase().includes(needle) ||
          it.category?.toLowerCase().includes(needle),
      );
    }
    let note: string | undefined;
    if (items.length > MENU_ITEM_CAP) {
      note = `showing ${MENU_ITEM_CAP} of ${items.length} matching items — pass a narrower filter to see the rest`;
      items = items.slice(0, MENU_ITEM_CAP);
    }
    return j({
      store_id: res.store_id,
      store_name: res.store_name,
      menu_id: res.menu_id,
      store_is_open: res.store_is_open,
      // Named by `menu --help` in 0.2.5 and matched by no CARRY_THROUGH token;
      // picked explicitly rather than widening the set with "open"/"time",
      // which would drag unrelated timestamp fields through every menu.
      store_next_open_time: res.store_next_open_time,
      total_items: total,
      returned_items: items.length,
      // Store-level promotions and order-ahead windows (dd-cli >=0.2.4/0.2.5).
      ...carryThrough(res, ["items"]),
      ...(note ? { note } : {}),
      items,
    });
  },

  async get_restaurant_item_details({ store_id, menu_id, item_id, address_id }) {
    const cleanId = String(item_id).replace(/^i_/, "");
    const res = await ddJson([
      "restaurant-item-details",
      "--store-id",
      String(store_id),
      "--menu-id",
      String(menu_id),
      "--item-id",
      cleanId,
      ...(await addressIdArgs(address_id)),
    ], { retryOnce: true });
    return j(res);
  },

  async get_store_details({ store_id }) {
    const res = await ddJson(["store-details", "--store-id", String(store_id)], { retryOnce: true });
    return j(res);
  },

  async list_carts({ store_id }) {
    const args = ["cart", "list"];
    if (store_id != null) args.push("--store-id", String(store_id));
    return j(await ddJson(args, { retryOnce: true }));
  },

  async add_items_to_cart({
    store_id,
    menu_id,
    items,
    cart_uuid,
    group_cart_url,
    fulfillment,
    group_cart,
    spend_limit_cents,
    guest_first_name,
    guest_last_name,
  }) {
    const cleaned = (items as any[]).map((it) => ({
      ...it,
      item_id: String(it.item_id).replace(/^i_/, ""),
    }));
    const args = [
      "cart",
      "add-items",
      "--store-id",
      String(store_id),
      "--menu-id",
      String(menu_id),
      "--items-json",
      JSON.stringify(cleaned),
    ];
    if (cart_uuid) args.push("--cart-uuid", String(cart_uuid));
    if (group_cart_url) args.push("--group-cart-url", String(group_cart_url));
    if (fulfillment) args.push("--fulfillment", String(fulfillment));
    if (group_cart) args.push("--group-cart");
    if (spend_limit_cents != null) args.push("--spend-limit-cents", String(spend_limit_cents));

    // ── Guest sub-cart ────────────────────────────────────────────────────
    // A guest never signs in: the host adds for them, tagged with their name
    // on the first add and with the token dd-cli returned on every add after.
    const isGuestAdd = Boolean(guest_first_name || guest_last_name);
    if (!isGuestAdd) return j(await ddJson(args));

    // dd-cli's own constraints, enforced here so a mistake costs a clear
    // message instead of a rejected call the model has to interpret.
    if (!guest_first_name || !guest_last_name) {
      return j({
        success: false,
        error: "A guest needs both guest_first_name and guest_last_name — that name is how Peckish tracks their sub-cart across adds.",
      });
    }
    if (!cart_uuid && !group_cart_url) {
      return j({
        success: false,
        error:
          "A guest can only be added to an EXISTING group cart: pass cart_uuid (or group_cart_url for the first add). Create the cart first with group_cart.",
      });
    }
    if (group_cart || spend_limit_cents != null) {
      return j({
        success: false,
        error:
          "group_cart and spend_limit_cents create a cart; a guest add always targets one that exists. Create the group cart first, then add guests to its cart_uuid.",
      });
    }

    const known = cart_uuid ? guestToken(String(cart_uuid), guest_first_name, guest_last_name) : null;
    args.push(
      "--guest-json",
      // Never send the name alongside a token — dd-cli treats the token as the
      // identity, and the name would be a second, conflicting one.
      known
        ? JSON.stringify({ guest_token: known })
        : JSON.stringify({ first_name: guest_first_name, last_name: guest_last_name }),
    );

    // Raw read: the token appears exactly once, on this response, and is
    // stripped from everything the model or the audit log ever sees.
    const raw = await ddJsonRaw(args);

    // A new guest is only durable once their token is filed against a cart.
    // Either half missing — no token in the response, or nothing to key it on
    // — means the next add for this name opens a SECOND sub-cart, so say so
    // rather than reporting a clean success.
    // Read once, whether or not this guest is new: a token that came back on
    // THIS response has to be scrubbed from the text below even when we already
    // had one on file, because dd-cli may echo it in a message field.
    const issued = findGuestToken(raw);
    let lostContinuity = false;
    if (!known) {
      const forCart = String(cart_uuid ?? raw.cart_uuid ?? "");
      if (issued && forCart) rememberGuest(forCart, guest_first_name, guest_last_name, issued);
      else lostContinuity = true;
    }

    const payload = j({
      ...(stripUiFields(raw) as Record<string, unknown>),
      guest: `${guest_first_name} ${guest_last_name}`,
      guest_add: known ? "existing guest" : "new guest",
      ...(lostContinuity
        ? {
            warning:
              "The items were added, but Peckish could not record this guest's sub-cart, so a later add under the same name would start a second one. Check show_cart before adding more for them.",
          }
        : {}),
      note: "Adds are additive, not idempotent: on a timeout or error, check item_errors[] before retrying — an item missing from it already went in, and retrying doubles it.",
    });
    // Belt to the stripper's braces: stripUiFields drops a `guest_token` KEY,
    // but a credential pasted into a free-text field is just a substring and
    // survives it. Redact by value before anything sees this.
    return redactGuestTokens(payload, [issued ?? "", known ?? ""]);
  },

  async list_cart_guests({ cart_uuid }) {
    const guests = listGuests(String(cart_uuid));
    return j({
      guests: guests.map((g) => g.name),
      note: guests.length
        ? "Guests Peckish is tracking on this cart. Real participants who joined with their own DoorDash login are NOT listed here — cart show has the line items."
        : "No guests tracked for this cart. Anyone who joined via the group cart link signed in themselves and is not a guest.",
    });
  },

  async show_cart({ cart_uuid }) {
    return j(await ddJson(["cart", "show", "--cart-uuid", String(cart_uuid)], { retryOnce: true }));
  },

  async remove_cart_item({ cart_uuid, cart_item_id }) {
    return j(
      await ddJson([
        "cart",
        "remove-item",
        "--cart-uuid",
        String(cart_uuid),
        "--cart-item-id",
        String(cart_item_id),
      ]),
    );
  },

  async delete_cart({ cart_uuid }) {
    const res = await ddJson(["cart", "delete", "--cart-uuid", String(cart_uuid)]);
    forgetCart(String(cart_uuid)); // the sub-carts died with it
    return j(res);
  },

  async preview_order({ cart_uuid, scheduled_time, include_work_benefits, selected_budget_id, fulfillment, priority, no_apply_credits }) {
    const base = ["order", "preview", "--cart-uuid", String(cart_uuid)];
    if (scheduled_time) base.push("--scheduled-time", String(scheduled_time));
    if (include_work_benefits) base.push("--include-work-benefits");
    if (selected_budget_id) base.push("--selected-budget-id", String(selected_budget_id));
    if (priority) base.push("--priority");
    if (no_apply_credits) base.push("--no-apply-credits");

    // Canonical human-facing summary first (per dd-cli guidance), then the
    // structured quote for programmatic fields, then the default card.
    // --fulfillment mutates the cart's mode, so it rides only on the first
    // call; the JSON re-read then reflects the already-updated mode.
    const summary = await ddBeautify(
      fulfillment ? [...base, "--fulfillment", String(fulfillment)] : base,
    );
    const raw = await ddJson(base, { retryOnce: true });
    const quote = (raw.quote ?? {}) as Record<string, any>;

    const trimmedQuote = {
      net_total_before_tip: quote.net_total_before_tip?.display_string,
      is_dashpass_applied: quote.is_dashpass_applied,
      is_pre_tippable: quote.is_pre_tippable,
      line_items: ((quote.line_items as any[]) ?? []).map((li) => ({
        label: li.label,
        amount: li.final_money?.display_string,
      })),
      tips_suggestion: (() => {
        const g = ((quote.tips_suggestion_details as any[]) ?? [])[0];
        if (!g) return null;
        const idx = g.default_index;
        const amounts = g.percentage_to_amount_monetary_values as any[] | undefined;
        if (idx == null || !amounts || !amounts[idx]) return null;
        return {
          suggested_cents: amounts[idx].unit_amount,
          suggested_percent: (g.percentage_values as any[] | undefined)?.[idx],
          recipient: g.tip_recipient,
        };
      })(),
      credits_applied: quote.credit_details?.total_credits_applied?.display_string,
      delivery_address: quote.delivery_address?.printable_address,
      fulfillment_type: quote.store_order_cart?.fulfillment_type,
      delivery_availability: quote.delivery_availability
        ? {
            asap_available: quote.delivery_availability.asap_available,
            asap_minutes: quote.delivery_availability.asap_minutes_range_string,
            asap_pickup_available: quote.delivery_availability.asap_pickup_available,
            scheduled_delivery_available: quote.delivery_availability.scheduled_delivery_available,
            is_within_delivery_region: quote.delivery_availability.is_within_delivery_region,
            // v0.2.1: PRIORITY entry here means express delivery is offered;
            // the requested option arrives marked when --priority was passed.
            delivery_options: quote.delivery_availability.delivery_options,
          }
        : undefined,
      pin_code_required: ((quote.dropoff_options as any[]) ?? []).some(
        (o) => o?.proof_of_delivery_type === "PIN_CODE",
      ),
      expense_order_options: quote.expense_order_options,
      team_id: quote.company_payment_info?.team_order_info?.team_id,
    };

    // Default card (dd-cli guidance: surface brand + last4 with every preview)
    let default_card: unknown = null;
    let payment_note: string | undefined;
    try {
      const pm = await ddJson(["payment-method", "list"], { retryOnce: true });
      const cards = (pm.cards as any[]) ?? [];
      const def = cards.find((c) => c.payment_method_id === pm.default_payment_method_id);
      default_card = def
        ? { brand: def.brand, last4: def.last4 }
        : null;
      if (!def)
        payment_note =
          "Default payment method is not a visible card (may be a wallet like Apple Pay). Confirm generically or offer checkout-url.";
    } catch {
      payment_note = "payment-method list failed — offer checkout-url so the user can verify their payment method.";
    }

    return j({
      display_summary: summary,
      quote: trimmedQuote,
      default_card,
      ...(payment_note ? { payment_note } : {}),
      success: raw.success,
      message: raw.message,
    });
  },

  async submit_order({
    cart_uuid,
    tip_cents,
    confirmation_summary,
    scheduled_time,
    fulfillment,
    priority,
    no_apply_credits,
    team_id,
    budget_id,
    team_account_id,
    expense_code,
    expense_notes,
  }) {
    // ── HARD HUMAN GATE ────────────────────────────────────────────────────
    const approved = await confirmOrderPlacement(
      String(confirmation_summary ?? `Cart ${cart_uuid}, tip ${tip_cents ?? 0}¢`),
    );
    if (!approved) {
      return j({
        success: false,
        declined_by_user: true,
        note: "The user declined at the terminal confirmation prompt. Do NOT retry submit unless they explicitly ask again.",
      });
    }
    const args = ["order", "submit", "--cart-uuid", String(cart_uuid), "--yes"];
    args.push("--tip-cents", String(tip_cents ?? 0));
    if (scheduled_time) args.push("--scheduled-time", String(scheduled_time));
    if (fulfillment) args.push("--fulfillment", String(fulfillment));
    if (priority) args.push("--priority");
    if (no_apply_credits) args.push("--no-apply-credits");
    if (team_id) args.push("--team-id", String(team_id));
    if (budget_id) args.push("--budget-id", String(budget_id));
    if (team_account_id) args.push("--team-account-id", String(team_account_id));
    if (expense_code) args.push("--expense-code", String(expense_code));
    if (expense_notes) args.push("--expense-notes", String(expense_notes));

    let submitRes: Record<string, unknown>;
    try {
      submitRes = await ddJson(args);
    } catch (err) {
      if (err instanceof DdCliError) {
        return j({
          success: false,
          error: err.message,
          detail: err.detail,
          note: "Submit is NOT idempotent. Check order_status / order history before any retry — the order may still have gone through.",
        });
      }
      throw err;
    }

    // Poll status until it leaves `pending` (bounded), per dd-cli guidance.
    const orderUuid = (submitRes.order_uuid ?? submitRes.order_id) as string | undefined;
    let finalStatus: Record<string, unknown> | null = null;
    if (orderUuid) {
      for (let i = 0; i < 8; i++) {
        await new Promise((r) => setTimeout(r, 5000));
        try {
          finalStatus = await ddJson(["order", "status", "--order-uuid", orderUuid], {
            retryOnce: true,
          });
          // Was `finalStatus.status`, which is always undefined — the status
          // sits at result.status, so this loop used to burn all 8 attempts
          // (40s) on every submit and never learn the outcome.
          if (!classifyOrderStatus(finalStatus).keep_polling) break;
        } catch {
          break;
        }
      }
    }
    if (classifyOrderStatus(finalStatus).order_created || submitRes.success === true) {
      forgetCart(String(cart_uuid)); // submit consumes the cart, guests and all
    }
    return j({
      submit_response: submitRes,
      final_status: finalStatus,
      lifecycle: classifyOrderStatus(finalStatus),
      note: "Only report the order as placed if lifecycle.order_created is true. The status lives at final_status.result.status ('placed', or a later delivery/pickup stage); there is no top-level status and no 'successful' value. On 'action_required' the user must finish verification in the DoorDash app; on 'order_declined' it did not go through; on 'cancelled' it was placed and then cancelled.",
    });
  },

  async get_checkout_url({ cart_uuid }) {
    return j(await ddJson(["order", "checkout-url", "--cart-uuid", String(cart_uuid)], { retryOnce: true }));
  },

  async get_order_history({ max, days, include_group_order }) {
    const args = ["order", "history"];
    if (max != null) args.push("--max", String(max));
    if (days != null) args.push("--days", String(days));
    // dd-cli >=0.2.3: also return group orders the user hosted or joined.
    if (include_group_order) args.push("--include-group-order");
    const res = await ddJson(args, { retryOnce: true });
    const orders = ((res.orders as any[]) ?? []).map((o) => ({
      order_uuid: o.order_uuid,
      store_id: o.store_id,
      store_name: o.store_name,
      // `created_at` never existed — 0.2.5 returns order_date and
      // order_fulfilled_at, so every history row used to come back undated.
      order_date: o.order_date,
      order_fulfilled_at: o.order_fulfilled_at,
      items: ((o.items as any[]) ?? []).map((it: any) =>
        typeof it === "string"
          ? it
          : { item_id: it.item_id, name: it.name, quantity: it.quantity, price: it.price },
      ),
      // Restaurant history rows carry no total on 0.2.5 — kept in case another
      // vertical does; get_receipt is the reliable source for money.
      total: o.total ?? o.order_total,
      is_reorderable: o.is_reorderable,
      fulfillment_type: o.fulfillment_type,
      order_target: o.order_target,
      // Group-order participation (dd-cli >=0.2.3) rides along when asked for.
      ...Object.fromEntries(
        Object.entries(o).filter(([k, v]) => /group/i.test(k) && v != null),
      ),
    }));
    return j({ orders, page_full: res.page_full });
  },

  async reorder({ order_uuid }) {
    return j(await ddJson(["order", "reorder", "--order-uuid", String(order_uuid)]));
  },

  async get_order_status({ order_uuid }) {
    const res = await ddJson(["order", "status", "--order-uuid", String(order_uuid)], { retryOnce: true });
    // Raw `result` rides along — it carries eta_trend, late_reason,
    // cancellation_reason and the actual delivery/pickup times.
    return j({ ...res, lifecycle: classifyOrderStatus(res) });
  },

  async get_receipt({ order_uuid }) {
    return j(await ddJson(["order", "receipt", "--order-uuid", String(order_uuid)], { retryOnce: true }));
  },

  async list_payment_methods() {
    const res = await ddJson(["payment-method", "list"], { retryOnce: true });
    const cards = ((res.cards as any[]) ?? []).map((c) => ({
      payment_method_id: c.payment_method_id,
      brand: c.brand,
      last4: c.last4,
      is_default: c.payment_method_id === res.default_payment_method_id,
    }));
    return j({
      cards,
      note: "cards[] shows credit/debit cards only — wallets (Apple Pay etc.) and gift cards are not visible here. Never conclude 'no payment method on file' from an empty list.",
    });
  },

  async list_promos({ store_id }) {
    return j(await ddJson(["promo", "list", "--store-id", String(store_id)], { retryOnce: true }));
  },

  async apply_promo({ cart_uuid, promo_code, campaign_id, ad_group_id, ad_id }) {
    const args = ["promo", "apply", "--cart-uuid", String(cart_uuid), "--promo-code", String(promo_code)];
    if (campaign_id) args.push("--campaign-id", String(campaign_id));
    if (ad_group_id) args.push("--ad-group-id", String(ad_group_id));
    if (ad_id) args.push("--ad-id", String(ad_id));
    return j(await ddJson(args));
  },

  async remove_promo({ cart_uuid, promo_code, campaign_id, ad_group_id, ad_id }) {
    const args = ["promo", "remove", "--cart-uuid", String(cart_uuid), "--promo-code", String(promo_code)];
    if (campaign_id) args.push("--campaign-id", String(campaign_id));
    if (ad_group_id) args.push("--ad-group-id", String(ad_group_id));
    if (ad_id) args.push("--ad-id", String(ad_id));
    return j(await ddJson(args));
  },

  async find_stores({ vertical, max, lat, lng, address_id }) {
    const args = ["find-nearby-stores"];
    if (vertical) args.push("--vertical", String(vertical));
    if (max != null) args.push("--max", String(max));
    // Unlike search, this command already defaults to the account address
    // server-side, so only an explicit override is passed.
    if (address_id) args.push("--address-id", String(address_id));
    else if (lat != null && lng != null) args.push("--lat", String(lat), "--lng", String(lng));
    return j(await ddJson(args, { retryOnce: true }));
  },

  async find_items({ store_id, queries }) {
    const args = ["find-items", "--store-id", String(store_id)];
    for (const q of queries as string[]) args.push("-q", String(q));
    return j(await ddJson(args, { retryOnce: true }));
  },

  async get_grocery_item_details({ store_id, item_id }) {
    return j(
      await ddJson(["item-details", "--store-id", String(store_id), "--item-id", String(item_id)], {
        retryOnce: true,
      }),
    );
  },

  async build_grocery_list({ items, store_id, desired_mx_name, servings }) {
    const args = ["build-grocery-list", "--items-json", JSON.stringify(items)];
    if (store_id) args.push("--store-id", String(store_id));
    if (desired_mx_name) args.push("--desired-mx-name", String(desired_mx_name));
    if (servings != null) args.push("--servings", String(servings));
    return j(await ddJson(args));
  },

  async start_signin() {
    // The user may have fixed it already (e.g. ran login in a terminal).
    let alreadyWorks = false;
    try {
      alreadyWorks = await probeSignin();
    } catch (err) {
      if (err instanceof DdCliError) return j({ signed_in: false, error: err.message });
      throw err;
    }
    if (alreadyWorks) {
      return j({ signed_in: true, note: "Sign-in already works — retry the request that failed." });
    }
    if (!loginInProgress()) {
      // Nothing to approve on a browserless host — say what actually works.
      if (!canBrowserSignin()) {
        return j({
          started: false,
          browser_signin_unavailable: true,
          note: signinHint(),
        });
      }
      const ok = await confirmAction(
        "DoorDash sign-in is missing or expired. Open the DoorDash sign-in flow in your browser now (runs `dd-cli login` locally)?",
      );
      if (!ok) {
        return j({
          started: false,
          declined_or_unavailable: true,
          note: "Sign-in was not approved on this surface. Ask the user to run `dd-cli login` in a terminal themselves, then retry the original request.",
        });
      }
      const launch = launchLogin();
      if (!launch.started) {
        return j({ started: false, browser_signin_unavailable: true, note: launch.reason });
      }
    }
    const res = await waitForSignin({ timeoutMs: 45_000, intervalMs: 3_000 });
    if (res.signedIn) {
      return j({ signed_in: true, note: "DoorDash sign-in verified — retry the request that failed." });
    }
    if (res.error) return j({ signed_in: false, error: res.error });
    return j({
      signed_in: false,
      login_in_progress: true,
      note: "The browser sign-in has not completed yet. Call start_signin again to keep waiting (it will NOT open another window), or ask the user whether they need more time.",
    });
  },

  async save_preference({ note }) {
    return j({ preferences: addPreference(String(note)) });
  },

  async remove_preference({ note }) {
    return j({ preferences: removePreference(String(note)) });
  },
};

// ---------------------------------------------------------------------------
// Tool schemas (Anthropic.Tool[])
// ---------------------------------------------------------------------------

const str = (description: string) => ({ type: "string" as const, description });
const num = (description: string) => ({ type: "number" as const, description });
const int = (description: string) => ({ type: "integer" as const, description });
const bool = (description: string) => ({ type: "boolean" as const, description });

const RAW_TOOLS: Anthropic.Tool[] = [
  {
    name: "list_addresses",
    description:
      "List the user's saved DoorDash delivery addresses (label, printable address, default flag). Use to resolve 'home'/'work' references. Delivery always uses the account default address.",
    input_schema: { type: "object", properties: {}, required: [] },
  },
  {
    name: "set_default_address",
    description:
      "Change the ACCOUNT-WIDE default delivery address (persists across app/web). Prompts the user y/N in the terminal before applying. Only call when the user asked to deliver somewhere else.",
    input_schema: {
      type: "object",
      properties: {
        address_id: str("addresses[].address_id from list_addresses"),
        printable_address: str("Human-readable address, shown in the confirmation prompt"),
      },
      required: ["address_id", "printable_address"],
    },
  },
  {
    name: "find_address",
    description:
      "Look up a street address the user typed and get back candidate addresses with place_ids. Use ONLY when the user wants to deliver somewhere not already in list_addresses — check that first. Nothing is saved: pass the chosen candidate's place_id to add_address.",
    input_schema: {
      type: "object",
      properties: {
        query: str("Address text as the user gave it, e.g. '1600 Amphitheatre Pkwy, Mountain View'"),
      },
      required: ["query"],
    },
  },
  {
    name: "add_address",
    description:
      "Save a candidate from find_address to the user's DoorDash account AND make it the ACCOUNT-WIDE default delivery address (persists across app/web). Prompts the user for approval first. Confirm the exact address with the user — including apartment/suite accuracy — before calling; a wrong address means a lost order.",
    input_schema: {
      type: "object",
      properties: {
        place_id: str("place_id of the chosen candidate from find_address"),
        printable_address: str("Human-readable address, shown in the confirmation prompt"),
      },
      required: ["place_id", "printable_address"],
    },
  },
  {
    name: "search_restaurants",
    description:
      "Search nearby restaurants by free-text query. Searches from the user's default saved address unless address_id or lat/lng is given. Returns store_id, name, distance, delivery_time estimate, rating, and pickup availability (offers_pickup, asap/scheduled_pickup_availability, next_open_time_asap_pickup_ms — use these before promising pickup). Stores with is_link_out=true cannot be ordered through this agent. Restaurant-focused — use find_stores for grocery/retail/pharmacy/pets/alcohol. Filters (dashpass_only, price_tier, distance_preference, max_eta_minutes) narrow server-side — prefer them over asking for 30 results and filtering by hand.",
    input_schema: {
      type: "object",
      properties: {
        query: str("Search text, e.g. 'grilled chicken bowls'"),
        address_id: str("Search from a saved address (list_addresses). Mutually exclusive with lat/lng; omit for the default address"),
        lat: num("Optional latitude override (pass with lng, and without address_id)"),
        lng: num("Optional longitude override (pass with lat, and without address_id)"),
        limit: int("Max results (default 8)"),
        dashpass_only: bool("Only DashPass stores. Pass when the user says they have DashPass and wants to use it"),
        price_tier: {
          type: "array",
          description: "Price tiers to include, 1 (cheapest) to 4 — e.g. [1,2] for 'somewhere cheap'",
          items: { type: "integer" },
        },
        distance_preference: {
          type: "string",
          enum: ["nearby", "balanced", "broad"],
          description: "How far to look: nearby for 'right around here', broad to widen a thin result set",
        },
        max_eta_minutes: int("Drop stores whose estimated delivery exceeds this many minutes — use when the user is in a hurry"),
      },
      required: ["query"],
    },
  },
  {
    name: "get_menu",
    description:
      "Fetch a restaurant's menu: returns menu_id (needed for cart adds and item details), store_is_open, the store's active promotions and which items qualify, order-ahead/schedule-ahead windows, and items with item_id, name, description, price, category, has_required_modifiers, orderability, and popularity (is_popular, popularity_rank, popular_modifications). Large menus are capped — pass `filter` (case-insensitive substring on name/description/category) to narrow.",
    input_schema: {
      type: "object",
      properties: {
        store_id: str("Store ID from search_restaurants or order history"),
        filter: str("Optional substring filter, e.g. 'chicken'"),
        address_id: str("Saved address to price promos against (default: the user's default address). Promo eligibility depends on the delivery location"),
      },
      required: ["store_id"],
    },
  },
  {
    name: "get_restaurant_item_details",
    description:
      "Full details for one restaurant menu item: price, description, any promotion it qualifies for, and extras[] customization groups (each with options[] holding option_id choices, min/max selections). REQUIRED before adding any item with has_required_modifiers. Pass selected options[].option_id values as nested_options when adding to cart (never extra_id).",
    input_schema: {
      type: "object",
      properties: {
        store_id: str("Restaurant store ID"),
        menu_id: str("menu_id from get_menu"),
        item_id: str("Item ID from get_menu (i_ prefix handled automatically)"),
        address_id: str("Saved address to price promos against (default: the user's default address)"),
      },
      required: ["store_id", "menu_id", "item_id"],
    },
  },
  {
    name: "get_store_details",
    description:
      "Store business metadata incl. printable_address — use when the user needs to know WHICH physical location a store is ('which Starbucks?').",
    input_schema: {
      type: "object",
      properties: { store_id: str("Store ID") },
      required: ["store_id"],
    },
  },
  {
    name: "list_carts",
    description:
      "List the user's open (unsubmitted) carts: cart_uuid, store, items, timestamps (epoch ms). ALWAYS check this before creating a cart at a store — only one open cart per store is allowed; if one exists, ask the user whether to extend or replace it.",
    input_schema: {
      type: "object",
      properties: { store_id: str("Optional: filter to one store") },
      required: [],
    },
  },
  {
    name: "add_items_to_cart",
    description:
      "Add items to a cart (creates one if no cart_uuid passed and none open at the store). Also the only way to add for a GUEST — see guest_first_name. APPEND semantics: re-adding an item_id SUMS quantities. Items need item_id + item_name + quantity; customizations go in nested_options[] (entries: id, name, quantity, optional recursive options[]). Weight-priced items (deli, butcher, produce) take a decimal quantity in their own unit — the final charge is by actual weight, so tell the user the price is an estimate. Items the merchant ships with default modifications keep them unless you pass default_handling 'exact'. On required-options failure the response lists required_options[] — ask the user to choose, then retry. Check list_carts first.",
    input_schema: {
      type: "object",
      properties: {
        store_id: str("Store ID the items belong to"),
        menu_id: str("Menu ID from get_menu (restaurants) or build_grocery_list/item details (grocery)"),
        items: {
          type: "array",
          description:
            'Items to add, e.g. [{"item_id":"123","item_name":"Salad","quantity":1,"nested_options":[{"id":"456","name":"Ranch","quantity":1}]}]',
          items: {
            type: "object",
            properties: {
              item_id: str("Menu item id"),
              item_name: str("Item display name"),
              quantity: num("Quantity — integer for count items, decimal in the item's unit for weight-priced items (0.5 = half a pound where the unit is lb)"),
              unit: str("Unit for a weight-priced item, as the menu/item details reported it (e.g. 'lb', 'kg'). Omit for count items"),
              default_handling: {
                type: "string",
                enum: ["default", "exact"],
                description:
                  "How to treat the merchant's default modifications on this item: 'default' (omit) keeps them; 'exact' takes the item with only the nested_options listed here. Only pass 'exact' when the user asked for a plain/unmodified version",
              },
              nested_options: {
                type: "array",
                description:
                  "Selected customization options. Each entry may carry its own options[] for combo sub-choices (max depth the CLI uses).",
                items: {
                  type: "object",
                  properties: {
                    id: str("option_id from item details"),
                    name: str("Option display name"),
                    quantity: num("Usually 1"),
                    options: {
                      type: "array",
                      description: "Sub-choices for combo options",
                      items: {
                        type: "object",
                        properties: {
                          id: str("Sub-option id"),
                          name: str("Sub-option name"),
                          quantity: num("Usually 1"),
                        },
                        required: ["id", "name", "quantity"],
                      },
                    },
                  },
                  required: ["id", "name", "quantity"],
                },
              },
            },
            required: ["item_id", "item_name", "quantity"],
          },
        },
        cart_uuid: str("Existing cart to append to (omit to create/append to store's open cart), or the group cart to add a guest to."),
        group_cart_url: str(
          "Join someone else's group cart from its shared link and add in one call. Use the cart_uuid the response returns for any later adds. Only for the signed-in user joining as themselves — a guest never joins.",
        ),
        fulfillment: { type: "string", enum: ["delivery", "pickup"], description: "Mode for a NEW cart (default delivery)" },
        group_cart: bool(
          "Create a shareable GROUP cart (no cart_uuid). Response carries group_cart_url — share it with participants. Not for joining one (use group_cart_url) and not for guest adds.",
        ),
        spend_limit_cents: int(
          "Per-participant spend limit in CENTS for a NEW host-pays group cart (2500 = $25). Requires group_cart; cannot combine with cart_uuid. Omit for unlimited. The host is exempt from their own limit.",
        ),
        guest_first_name: str(
          "Add these items for a GUEST — someone with no DoorDash account, whose items sit in their own sub-cart of a group cart the signed-in user hosts. Pass with guest_last_name and the group cart's cart_uuid. Peckish remembers the guest by name, so pass the same name for every later add and their items stay together.",
        ),
        guest_last_name: str("Guest's last name (required whenever guest_first_name is given)"),
      },
      required: ["store_id", "menu_id", "items"],
    },
  },
  {
    name: "list_cart_guests",
    description:
      "Names of the guests Peckish is tracking on a group cart — people with no DoorDash account whose items the host added for them. Use to answer 'who has ordered?' and to check a name before adding again (same name = same sub-cart). Real participants who joined with their own login are not listed; their items show in show_cart.",
    input_schema: {
      type: "object",
      properties: { cart_uuid: str("Group cart UUID") },
      required: ["cart_uuid"],
    },
  },
  {
    name: "show_cart",
    description:
      "Show cart contents (no pricing — use preview_order for that). items[].id is the cart-LINE id used by remove_cart_item; items[].item_id is the menu item id. Don't swap them.",
    input_schema: {
      type: "object",
      properties: { cart_uuid: str("Cart UUID") },
      required: ["cart_uuid"],
    },
  },
  {
    name: "remove_cart_item",
    description: "Remove one line item from a cart. cart_item_id = items[].id from show_cart (NOT the menu item_id).",
    input_schema: {
      type: "object",
      properties: {
        cart_uuid: str("Cart UUID"),
        cart_item_id: str("Cart-line id from show_cart items[].id"),
      },
      required: ["cart_uuid", "cart_item_id"],
    },
  },
  {
    name: "delete_cart",
    description:
      "Empty a cart and abandon it (cart_uuid becomes invalid). Only on user request/consent — e.g. replacing a stale cart at the same store.",
    input_schema: {
      type: "object",
      properties: { cart_uuid: str("Cart UUID to abandon") },
      required: ["cart_uuid"],
    },
  },
  {
    name: "preview_order",
    description:
      "Authoritative pricing + logistics for a cart (read-only, no charge): display_summary (show VERBATIM to the user), quote {net_total_before_tip = the real total, line_items fee breakdown, tips_suggestion (cents), delivery_availability ETAs, credits, PIN requirement, work budgets}, and the default card (brand+last4). Re-run after ANY cart change. Pass include_work_benefits when the user mentions work/office/company/team/expense or delivers to a Work address. Budget checks: compare the user's cap against net_total_before_tip (tip adds on top).",
    input_schema: {
      type: "object",
      properties: {
        cart_uuid: str("Cart UUID"),
        scheduled_time: str("ISO 8601 UTC (e.g. 2026-07-19T23:00:00Z) for scheduled delivery; omit for ASAP"),
        include_work_benefits: bool("Set on ANY work/company/team/expense signal"),
        selected_budget_id: str("Apply a specific work budget id from a prior preview"),
        fulfillment: {
          type: "string",
          enum: ["delivery", "pickup"],
          description: "MUTATES the cart's mode before pricing — only pass when the user explicitly asked to switch",
        },
        priority: bool(
          "Request Priority (express) delivery — a paid, faster upgrade. Delivery-only; incompatible with pickup and scheduled_time. Verify quote.delivery_availability.delivery_options[] contains delivery_option_type 'PRIORITY' before promising it; pass the same flag at submit.",
        ),
        no_apply_credits: bool(
          "Opt OUT of applying DoorDash credits (they apply by default — do not prompt about them). Pass ONLY when the user explicitly asks not to use credits; all-or-nothing; pass the same flag at submit.",
        ),
      },
      required: ["cart_uuid"],
    },
  },
  {
    name: "submit_order",
    description:
      "Place the order — charges the user's real payment method. HARD GATE: the terminal asks the user to type 'yes'; a decline returns declined_by_user. Call ONLY after: (1) preview shown, (2) tip explicitly confirmed (delivery; pickup = 0 without asking), (3) payment method named to the user, (4) the user clearly said to place it. NOT idempotent — never retry without checking get_order_status first. Report success only when the response's lifecycle.order_created is true.",
    input_schema: {
      type: "object",
      properties: {
        cart_uuid: str("Cart UUID"),
        tip_cents: int("Dasher tip in CENTS (500 = $5.00). 0 only on explicit decline or pickup."),
        confirmation_summary: str(
          "Short human-readable summary shown at the terminal gate: store, items, total, tip, card (brand+last4), ETA",
        ),
        scheduled_time: str("Must match the value used in preview, if any"),
        fulfillment: { type: "string", enum: ["delivery", "pickup"], description: "Only to match a mode explicitly set at preview" },
        priority: bool("MUST match the preview: pass iff the previewed quote used priority"),
        no_apply_credits: bool("MUST match the preview: pass iff the user opted out of credits there"),
        team_id: str("Work benefits: quote.team_id from preview"),
        budget_id: str("Work benefits: chosen budget id"),
        team_account_id: str("Work benefits: budget's team_account_id when present"),
        expense_code: str("Required when budget expense_code_mode != NONE"),
        expense_notes: str("Required when budget is_expense_note_required"),
      },
      required: ["cart_uuid", "tip_cents", "confirmation_summary"],
    },
  },
  {
    name: "get_checkout_url",
    description:
      "Browser checkout URL for a cart — FALLBACK ONLY, for edits the CLI can't make: swap payment method, opt out of credits, change address mid-checkout, enter a promo code, or finish an age-restricted order. Do not offer by default after previews.",
    input_schema: {
      type: "object",
      properties: { cart_uuid: str("Cart UUID") },
      required: ["cart_uuid"],
    },
  },
  {
    name: "get_order_history",
    description:
      "Past orders (default 50 orders / 90 days, max 100 / 365): store, items (item_id, name, quantity), order_date, order_fulfilled_at, order_uuid, is_reorderable, fulfillment_type, is_group_order. Rows carry no total and no per-item price — use get_receipt for money. Use to analyze habits ('my usual'), find reorder targets, or locate a specific past order (scan all results; if page_full, re-query higher/wider).",
    input_schema: {
      type: "object",
      properties: {
        max: int("Max orders 1-100 (default 50)"),
        days: int("Window in days, up to 365 (default 90)"),
        include_group_order: bool("Also return group orders the user hosted or joined — pass when the question is about a team/office/shared order"),
      },
      required: [],
    },
  },
  {
    name: "reorder",
    description:
      "Create a NEW cart from a past order. Check list_carts for the store first (one open cart per store). Afterwards ALWAYS preview_order and diff items vs the original — out-of-stock items drop silently; call out any drops before asking about submitting.",
    input_schema: {
      type: "object",
      properties: { order_uuid: str("From get_order_history orders[].order_uuid") },
      required: ["order_uuid"],
    },
  },
  {
    name: "get_order_status",
    description:
      "Track a submitted order. The order is under `result` (result.status, plus quoted/actual_delivery_time, actual_pickup_time, eta_trend, late_reason, cancellation_reason, merchant_name, is_pickup) — read the derived `lifecycle` block rather than matching status text: order_created, is_terminal, keep_polling, not_found. Statuses: pending (check again) | placed (created successfully) | scheduled/store_confirmed/ready_for_pickup/dasher_assigned/dasher_at_store/picked_up/dasher_nearby (delivery or pickup underway) | completed | cancelled | action_required (user must verify in app) | order_declined. Answer 'where is my order?' from this rather than guessing from the submit response.",
    input_schema: {
      type: "object",
      properties: { order_uuid: str("From submit response or order history") },
      required: ["order_uuid"],
    },
  },
  {
    name: "get_receipt",
    description: "Itemized receipt for one past order (subtotal, fees, tax, tip, total, card last4). Sensitive — show only to the user.",
    input_schema: {
      type: "object",
      properties: { order_uuid: str("Order UUID") },
      required: ["order_uuid"],
    },
  },
  {
    name: "list_payment_methods",
    description:
      "Saved cards + which is default. Cards ONLY — wallets/gift cards are invisible here; never conclude 'no payment method' from an empty list (offer checkout-url instead).",
    input_schema: { type: "object", properties: {}, required: [] },
  },
  {
    name: "list_promos",
    description:
      "Campaign promos eligible at a store for this user (may be empty — that's normal). To apply one to a cart use apply_promo with all four ids; preview_order shows what's actually discounting a cart.",
    input_schema: {
      type: "object",
      properties: { store_id: str("Store ID") },
      required: ["store_id"],
    },
  },
  {
    name: "apply_promo",
    description:
      "Apply a promo to a cart. Campaign promos from list_promos need promo_code + campaign_id + ad_group_id + ad_id; user-typed codes need only promo_code. On failure: check subtotal vs the promo's stated minimum. Re-preview after.",
    input_schema: {
      type: "object",
      properties: {
        cart_uuid: str("Cart UUID"),
        promo_code: str("Code string"),
        campaign_id: str("Campaign promos only"),
        ad_group_id: str("Campaign promos only"),
        ad_id: str("Campaign promos only"),
      },
      required: ["cart_uuid", "promo_code"],
    },
  },
  {
    name: "remove_promo",
    description: "Remove an applied promo (pass the same ids used at apply). Re-preview after.",
    input_schema: {
      type: "object",
      properties: {
        cart_uuid: str("Cart UUID"),
        promo_code: str("Code to remove"),
        campaign_id: str("If used at apply"),
        ad_group_id: str("If used at apply"),
        ad_id: str("If used at apply"),
      },
      required: ["cart_uuid", "promo_code"],
    },
  },
  {
    name: "find_stores",
    description:
      "Discover NON-restaurant stores near the default address (16-mile radius): grocery (default), alcohol, convenience, pets, retail, or nv (all non-restaurant). distance_meters is meters — divide by 1609 for miles. Restaurant queries belong in search_restaurants.",
    input_schema: {
      type: "object",
      properties: {
        vertical: {
          type: "string",
          enum: ["grocery", "alcohol", "convenience", "pets", "retail", "nv"],
          description: "Merchant type (default grocery)",
        },
        max: int("Max stores (default 10)"),
        address_id: str("Saved address to search from (list_addresses). Mutually exclusive with lat/lng"),
        lat: num("Optional latitude override (pass with lng, and without address_id)"),
        lng: num("Optional longitude override (pass with lat, and without address_id)"),
      },
      required: [],
    },
  },
  {
    name: "find_items",
    description:
      "Search items inside ONE retail/grocery store by name — returns item_ids for cart adds, keyed per query. Empty for restaurants (use get_menu there).",
    input_schema: {
      type: "object",
      properties: {
        store_id: str("Retail/grocery store ID"),
        queries: {
          type: "array",
          items: { type: "string" },
          description: "One or more item names, e.g. ['milk','eggs']",
        },
      },
      required: ["store_id", "queries"],
    },
  },
  {
    name: "get_grocery_item_details",
    description:
      "Details for a retail/grocery item (pricing, options) + menu_id fallback source for grocery cart adds. Restaurants: use get_restaurant_item_details.",
    input_schema: {
      type: "object",
      properties: {
        store_id: str("Store ID"),
        item_id: str("Item ID from find_items or build_grocery_list"),
      },
      required: ["store_id", "item_id"],
    },
  },
  {
    name: "build_grocery_list",
    description:
      "Resolve a grocery/pantry list to real products at one store (raw ingredients only — NOT restaurant food). STATELESS: every call REPLACES the list, so always send the complete list. Weight items take decimal quantity (0.5 = half lb) only when purchase_type is MEASUREMENT; eggs are per dozen. Verify resolved items[].name with the user before carting. Vague asks: cap at 20 items and show your picks.",
    input_schema: {
      type: "object",
      properties: {
        items: {
          type: "array",
          description: '[{"name":"milk"},{"name":"ground beef","quantity":0.5}]',
          items: {
            type: "object",
            properties: { name: str("Item name"), quantity: num("Count, or weight for measurement items (default 1)") },
            required: ["name"],
          },
        },
        store_id: str("Pin to a store (takes precedence over desired_mx_name)"),
        desired_mx_name: str("Preferred merchant name, e.g. 'Whole Foods'"),
        servings: int("Only when the user says 'for N people' — display-only"),
      },
      required: ["items"],
    },
  },
  {
    name: "start_signin",
    description:
      "Fix a broken DoorDash sign-in WITHOUT sending the user to a terminal. Call when a tool fails with 'sign-in is missing or expired' AND the user wants to continue: after they approve a confirmation prompt, this launches `dd-cli login` (opens their browser) and polls until the sign-in works, up to ~45s per call. If it returns login_in_progress, call it again to keep waiting — repeat calls never open a second window. On signed_in, retry the request that originally failed. On browser_signin_unavailable (headless Linux container/VM: no browser to sign in with) do NOT call it again — relay its note, which tells the user how to inject a DD_CLI_ACCESS_TOKEN instead.",
    input_schema: { type: "object", properties: {}, required: [] },
  },
  {
    name: "save_preference",
    description:
      "Persist a durable user preference across sessions (dietary rule, allergy, budget habit, tip default). Save when the user states one ('no mushrooms ever', 'I usually tip 20%'). Keep each note short and self-contained.",
    input_schema: {
      type: "object",
      properties: { note: str("The preference, e.g. 'Avoid mushrooms in all dishes'") },
      required: ["note"],
    },
  },
  {
    name: "remove_preference",
    description:
      "Delete one saved user preference when the user retracts or reverses it ('actually, mushrooms are fine now', 'stop defaulting to pickup'). Pass the note's exact stored text — as listed in the session context or returned by save_preference — since matching is by exact text (case-insensitive). Returns the remaining preferences so you can confirm what's still active.",
    input_schema: {
      type: "object",
      properties: {
        note: str("The exact text of the stored preference note to delete, e.g. 'Avoid mushrooms in all dishes'"),
      },
      required: ["note"],
    },
  },
];

// ---------------------------------------------------------------------------
// Strict mode: the API then guarantees tool inputs validate against the schema
// (no malformed-argument class at all). Strict requires additionalProperties:
// false and a required[] on every object node — applied mechanically here so
// no hand-written schema can drift out of compliance.
// ---------------------------------------------------------------------------

export function strictifySchema<T>(node: T): T {
  if (Array.isArray(node)) return node.map(strictifySchema) as T;
  if (node && typeof node === "object") {
    const obj = { ...(node as Record<string, unknown>) };
    for (const [k, v] of Object.entries(obj)) obj[k] = strictifySchema(v);
    if (obj.type === "object") {
      obj.additionalProperties = false;
      if (!Array.isArray(obj.required)) obj.required = [];
      if (!obj.properties) obj.properties = {};
    }
    return obj as T;
  }
  return node;
}

/**
 * dd-cli ≥0.2.1 requires --intent on every command. Injected mechanically as a
 * required param on every tool so the model supplies it once per call; the
 * dispatcher routes it to the wrapper (see setCallIntent). Peckish's privacy
 * default sends this goal summary WITHOUT the user's verbatim words.
 */
export const INTENT_PARAM_DESCRIPTION =
  "One short line stating who this is for and the goal, e.g. 'Help the user order dinner'. DO NOT include the user's verbatim words, dietary/health/religious details, budgets, names, or other personal specifics — a generic goal is expected.";

function withIntentParam(schema: Anthropic.Tool.InputSchema): Anthropic.Tool.InputSchema {
  const properties = {
    ...(schema.properties as Record<string, unknown>),
    intent: { type: "string", description: INTENT_PARAM_DESCRIPTION },
  };
  const required = Array.from(new Set([...((schema.required as string[]) ?? []), "intent"]));
  return { ...schema, properties, required };
}

export const tools: Anthropic.Tool[] = RAW_TOOLS.map((t) => ({
  ...t,
  strict: true,
  input_schema: strictifySchema(withIntentParam(t.input_schema)),
}));

export function preferencesForPrompt(): string {
  const notes = listPreferences();
  return notes.length ? notes.map((n) => `- ${n}`).join("\n") : "(none saved yet)";
}
