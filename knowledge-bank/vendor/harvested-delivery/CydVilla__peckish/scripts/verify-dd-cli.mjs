#!/usr/bin/env node
/**
 * Check Peckish's assumptions against the dd-cli you actually have installed.
 *
 * Peckish's flags for dd-cli 0.2.3-0.2.5 were implemented from the published
 * release notes, which describe the features but do not always name the
 * response fields. This script closes that gap on a machine with a real,
 * signed-in dd-cli: it runs the commands Peckish runs, reports whether each
 * flag is accepted, and prints the field names the responses actually carry
 * so the guesses can be replaced with certainty.
 *
 *   node scripts/verify-dd-cli.mjs
 *   node scripts/verify-dd-cli.mjs --store-id <id>   # skip search, go straight to a store
 *
 * READ-ONLY. It never creates a cart, saves an address, applies a promo or
 * submits an order; the only commands it runs are lookups. It does send
 * --intent on each one, like any other dd-cli call.
 */
import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const INTENT =
  'Summary: Verify which dd-cli features this installation supports.\nuser prompt/purpose: "(not shared — Peckish verification script)"';

const DD_CLI =
  [
    process.env.DD_CLI_PATH,
    join(homedir(), ".local", "bin", "dd-cli"),
    "/usr/local/bin/dd-cli",
  ].find((p) => p && existsSync(p)) ?? "dd-cli";

const args = process.argv.slice(2);
const argValue = (name) => {
  const i = args.indexOf(name);
  return i === -1 ? undefined : args[i + 1];
};

const GREEN = "\x1b[32m";
const RED = "\x1b[31m";
const YELLOW = "\x1b[33m";
const DIM = "\x1b[2m";
const OFF = "\x1b[0m";

const results = [];
const record = (feature, ok, detail) => {
  results.push({ feature, ok, detail });
  const mark = ok === true ? `${GREEN}PASS${OFF}` : ok === false ? `${RED}FAIL${OFF}` : `${YELLOW}SKIP${OFF}`;
  console.log(`  ${mark}  ${feature}${detail ? `\n        ${DIM}${detail}${OFF}` : ""}`);
};

function run(argv, { json = true } = {}) {
  const full = json ? ["--json-output", ...argv, "--intent", INTENT] : argv;
  return new Promise((resolve) => {
    execFile(DD_CLI, full, { timeout: 90_000, maxBuffer: 32 * 1024 * 1024 }, (err, stdout, stderr) => {
      if (err) return resolve({ ok: false, error: `${stdout}\n${stderr}`.trim() || err.message });
      if (!json) return resolve({ ok: true, text: stdout });
      try {
        const env = JSON.parse(stdout);
        resolve({ ok: true, payload: env.structuredContent ?? {}, isError: env.isError });
      } catch {
        resolve({ ok: false, error: `non-JSON output: ${stdout.slice(0, 300)}` });
      }
    });
  });
}

/** Key names anywhere in a payload that look like the concept we're after. */
function keysMatching(value, pattern, found = new Set(), depth = 0) {
  if (depth > 6 || !value || typeof value !== "object") return found;
  for (const [k, v] of Object.entries(value)) {
    if (pattern.test(k)) found.add(k);
    keysMatching(v, pattern, found, depth + 1);
  }
  return found;
}

const list = (set) => (set.size ? [...set].join(", ") : "(none seen — may need a store that has one)");

console.log(`\ndd-cli under test: ${DD_CLI}\n`);

// --- version ---------------------------------------------------------------
console.log("Version");
const versionRes = await run(["--version"], { json: false });
const version = versionRes.ok ? (versionRes.text.match(/v?(\d+\.\d+\.\d+)\b/)?.[1] ?? null) : null;
record(
  "--version reports a parseable version",
  Boolean(version),
  version ? `parsed "${version}" from: ${versionRes.text.trim()}` : `output: ${versionRes.text ?? versionRes.error}`,
);
if (version) {
  console.log(`  ${DIM}Peckish's detector would read this as ${version}.${OFF}`);
}

// --- addresses (0.2.3, 0.2.4) ---------------------------------------------
console.log("\nAddresses");
const addresses = await run(["address", "list"]);
const saved = addresses.ok ? (addresses.payload.addresses ?? []) : [];
record("address list", addresses.ok && saved.length > 0, addresses.ok ? `${saved.length} saved` : addresses.error);
const defaultAddress = saved.find((a) => a.is_default) ?? saved[0];
if (!defaultAddress) {
  console.error(
    `\n${RED}Cannot continue without a saved address.${OFF} Sign in with \`dd-cli login\` and add one in the DoorDash app.\n`,
  );
  process.exit(1);
}
console.log(`  ${DIM}using address_id ${defaultAddress.address_id} (${defaultAddress.printable_address})${OFF}`);

const findAddr = await run(["address", "find", "--query", defaultAddress.printable_address]);
record(
  "address find --query (0.2.3)",
  findAddr.ok,
  findAddr.ok
    ? `candidate keys: ${list(keysMatching(findAddr.payload, /place_id|address/i))}`
    : findAddr.error,
);
console.log(`  ${DIM}address add --place-id is a mutation; not exercised here.${OFF}`);

// --- search (0.2.4 address-id, 0.2.5 filters) ------------------------------
console.log("\nSearch");
const plainSearch = await run(["search", "-q", "ramen", "--address-id", defaultAddress.address_id, "--limit", "5"]);
record("search --address-id (0.2.4)", plainSearch.ok, plainSearch.ok ? undefined : plainSearch.error);

const stores = plainSearch.ok ? (plainSearch.payload.stores ?? []) : [];
if (stores.length) {
  const pickupKeys = keysMatching(stores[0], /pickup/i);
  const aheadKeys = keysMatching(stores[0], /ahead|schedul/i);
  record("search results carry pickup availability (0.2.5)", pickupKeys.size > 0, `keys: ${list(pickupKeys)}`);
  record("search results carry order-ahead fields (0.2.5)", aheadKeys.size > 0, `keys: ${list(aheadKeys)}`);
  console.log(`  ${DIM}all store keys: ${Object.keys(stores[0]).join(", ")}${OFF}`);
}

for (const [label, extra] of [
  ["--dashpass-only", ["--dashpass-only"]],
  ["--price-tier (repeated)", ["--price-tier", "1", "--price-tier", "2"]],
  ["--distance-preference", ["--distance-preference", "nearby"]],
  ["--max-eta-minutes", ["--max-eta-minutes", "45"]],
]) {
  const res = await run(["search", "-q", "ramen", "--address-id", defaultAddress.address_id, "--limit", "3", ...extra]);
  record(`search ${label} (0.2.5)`, res.ok, res.ok ? undefined : res.error);
}

// --- menu + item details (0.2.4 promos) ------------------------------------
console.log("\nMenus and promotions");
const storeId = argValue("--store-id") ?? stores[0]?.store_id;
if (!storeId) {
  record("menu --address-id (0.2.4)", null, "no store to test against — pass --store-id <id>");
} else {
  const menu = await run(["menu", "--store-id", String(storeId), "--address-id", defaultAddress.address_id]);
  record("menu --address-id (0.2.4)", menu.ok, menu.ok ? undefined : menu.error);
  if (menu.ok) {
    const promoKeys = keysMatching(menu.payload, /promo|discount|deal|savings/i);
    record("menu carries promotions (0.2.4)", promoKeys.size > 0, `keys: ${list(promoKeys)}`);
    console.log(`  ${DIM}top-level menu keys: ${Object.keys(menu.payload).join(", ")}${OFF}`);

    const items = menu.payload.items ?? [];
    const weightItem = items.find((it) => keysMatching(it, /weight|measurement|purchase_type/i).size > 0);
    record(
      "menu items expose weight pricing (0.2.5)",
      weightItem ? true : null,
      weightItem
        ? `keys: ${list(keysMatching(weightItem, /weight|unit|measurement|purchase/i))}`
        : "no weight-priced item on this menu — try a grocery/butcher store",
    );
    if (items[0]) console.log(`  ${DIM}sample item keys: ${Object.keys(items[0]).join(", ")}${OFF}`);

    const first = items[0];
    if (first && menu.payload.menu_id) {
      const details = await run([
        "restaurant-item-details",
        "--store-id",
        String(storeId),
        "--menu-id",
        String(menu.payload.menu_id),
        "--item-id",
        String(first.item_id).replace(/^i_/, ""),
        "--address-id",
        defaultAddress.address_id,
      ]);
      record("restaurant-item-details --address-id (0.2.4)", details.ok, details.ok ? undefined : details.error);
      if (details.ok) {
        const k = keysMatching(details.payload, /promo|discount|deal/i);
        record("item details carry promotions (0.2.4)", k.size > 0, `keys: ${list(k)}`);
      }
    }
  }
}

// --- order history + status (0.2.3) ----------------------------------------
console.log("\nOrder history and tracking");
const history = await run(["order", "history", "--max", "5", "--include-group-order"]);
record("order history --include-group-order (0.2.3)", history.ok, history.ok ? undefined : history.error);
const orders = history.ok ? (history.payload.orders ?? []) : [];
if (orders.length) {
  const groupKeys = keysMatching(orders[0], /group/i);
  record("history rows expose group-order fields (0.2.3)", groupKeys.size > 0 ? true : null, `keys: ${list(groupKeys)}`);
  console.log(`  ${DIM}sample order keys: ${Object.keys(orders[0]).join(", ")}${OFF}`);

  const status = await run(["order", "status", "--order-uuid", String(orders[0].order_uuid)]);
  record("order status (0.2.3 shape)", status.ok, status.ok ? undefined : status.error);
  if (status.ok) console.log(`  ${DIM}status keys: ${Object.keys(status.payload).join(", ")}${OFF}`);
} else {
  record("history rows expose group-order fields (0.2.3)", null, "no past orders on this account");
}

// --- summary ---------------------------------------------------------------
const failed = results.filter((r) => r.ok === false);
const skipped = results.filter((r) => r.ok === null);
console.log(
  `\n${failed.length ? RED : GREEN}${results.length - failed.length - skipped.length} passed${OFF}, ` +
    `${failed.length ? RED : DIM}${failed.length} failed${OFF}, ${DIM}${skipped.length} skipped${OFF}\n`,
);
if (failed.length) {
  console.log("Failures mean Peckish is sending something this dd-cli does not accept:");
  for (const f of failed) console.log(`  • ${f.feature}`);
  console.log(
    "\nOpen an issue with the output above — the flag names came from the release notes and may differ.\n",
  );
}
console.log(
  `${DIM}Field-name output above is the useful part: src/tools.ts matches promo/order-ahead/weight\n` +
    `keys by name pattern (CARRY_THROUGH_TOKENS). If real keys fall outside it, add them there.${OFF}\n`,
);
process.exit(failed.length ? 1 : 0);
