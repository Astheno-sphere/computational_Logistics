/**
 * Guest sub-cart tokens for group carts.
 *
 * A group cart can hold items for people who never sign in to DoorDash: the
 * authenticated host adds on their behalf with `--guest-json`. The first add
 * for a new guest returns a `guest_token` on that sub-cart, and that is the
 * ONLY time it ever appears — `cart show` never echoes it, and there is no
 * endpoint to fetch it again. Every later add for the same person must send
 * that token back.
 *
 * So Peckish stores it here, keyed by cart and guest name, and the model never
 * sees it. That is deliberate, not incidental: the token is a bearer
 * credential for one person's sub-cart, and dd-cli's own guidance is to keep
 * it server-side and out of logs. Peckish's audit log records a preview of
 * every tool result, so a token that reached the model would reach the disk
 * too. The model refers to a guest by name; this module does the rest.
 *
 * Stored at ~/.peckish/guests.json, 0600, because losing the file means
 * losing continuity for every open guest sub-cart — the only recovery is to
 * start the guest again under the same name, which forks their line items.
 */
import { homedir } from "node:os";
import { join } from "node:path";
import { mkdirSync, readFileSync, writeFileSync, existsSync, chmodSync } from "node:fs";

const DIR = join(homedir(), ".peckish");
const FILE = join(DIR, "guests.json");

/** Guest sub-carts outlive a session but not a month; pruned on every write. */
const MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;

export interface GuestRecord {
  first_name: string;
  last_name: string;
  guest_token: string;
  added_at: number;
}

interface GuestsFile {
  /** cart_uuid -> guest key -> record */
  carts: Record<string, Record<string, GuestRecord>>;
}

/** Guests are matched case- and spacing-insensitively on their full name. */
export function guestKey(firstName: string, lastName: string): string {
  return `${firstName} ${lastName}`.trim().toLowerCase().replace(/\s+/g, " ");
}

function load(): GuestsFile {
  try {
    if (existsSync(FILE)) {
      const parsed = JSON.parse(readFileSync(FILE, "utf8")) as GuestsFile;
      if (parsed && typeof parsed.carts === "object" && parsed.carts) return { carts: parsed.carts };
    }
  } catch {
    // Corrupt store — start fresh rather than crash a live order.
  }
  return { carts: {} };
}

function save(data: GuestsFile): void {
  const cutoff = Date.now() - MAX_AGE_MS;
  for (const [cart, guests] of Object.entries(data.carts)) {
    for (const [key, rec] of Object.entries(guests)) {
      if (!rec?.added_at || rec.added_at < cutoff) delete guests[key];
    }
    if (!Object.keys(guests).length) delete data.carts[cart];
  }
  mkdirSync(DIR, { recursive: true, mode: 0o700 });
  writeFileSync(FILE, JSON.stringify(data, null, 2) + "\n", { encoding: "utf8", mode: 0o600 });
  try {
    chmodSync(FILE, 0o600); // an existing file keeps its old mode without this
  } catch {
    // best-effort
  }
}

/** The stored token for this guest on this cart, or null if they're new. */
export function guestToken(cartUuid: string, firstName: string, lastName: string): string | null {
  return load().carts[cartUuid]?.[guestKey(firstName, lastName)]?.guest_token ?? null;
}

export function rememberGuest(
  cartUuid: string,
  firstName: string,
  lastName: string,
  token: string,
): void {
  const data = load();
  data.carts[cartUuid] ??= {};
  data.carts[cartUuid][guestKey(firstName, lastName)] = {
    first_name: firstName,
    last_name: lastName,
    guest_token: token,
    added_at: Date.now(),
  };
  save(data);
}

/** Names only — callers must never be handed the tokens. */
export function listGuests(cartUuid: string): Array<{ name: string; added_at: number }> {
  const guests = load().carts[cartUuid] ?? {};
  return Object.values(guests)
    .map((g) => ({ name: `${g.first_name} ${g.last_name}`.trim(), added_at: g.added_at }))
    .sort((a, b) => a.added_at - b.added_at);
}

/** Drop a cart's guests once it is submitted or abandoned. */
export function forgetCart(cartUuid: string): void {
  const data = load();
  if (!data.carts[cartUuid]) return;
  delete data.carts[cartUuid];
  save(data);
}

export function guestsFilePath(): string {
  return FILE;
}
