/**
 * Containment tests for the guest sub-cart token.
 *
 * `guest_token` is a bearer credential for one guest's sub-cart. dd-cli issues
 * it exactly once and cannot reissue it, and its own guidance is to keep it
 * server-side and out of logs. Peckish's claim is stronger than "we don't print
 * it": the token must never reach the model, and never reach the audit log,
 * which previews every tool result to disk.
 *
 * A test that only checks the happy path proves nothing about a credential —
 * the interesting question is what happens when dd-cli returns it somewhere
 * Peckish did not anticipate. So these drive the fake binary through shapes the
 * code was NOT written for (FAKE_DD_CLI_GUEST_SCENARIO): a camelCase key, the
 * value echoed inside free text, nesting past the finder's depth cap, an array,
 * and a non-zero exit that puts the credential in stderr.
 *
 * In every case two things must hold:
 *   1. the token does not appear in what the handler returns, and
 *   2. it does not appear in the audit log written from that result.
 * Losing continuity is an acceptable failure; leaking the credential is not.
 */
import { test, before, beforeEach, after } from "node:test";
import assert from "node:assert/strict";
import { chmodSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const FAKE = fileURLToPath(new URL("./fixtures/fake-dd-cli.mjs", import.meta.url));
const workdir = mkdtempSync(join(tmpdir(), "peckish-guest-"));
const LOG = join(workdir, "argv.log");

/** Must match GUEST_TOKEN in the fixture. */
const TOKEN = "gtok_secret_abc123";

process.env.DD_CLI_PATH = FAKE;
process.env.FAKE_DD_CLI_LOG = LOG;
process.env.FAKE_DD_CLI_VERSION = "0.2.5";
process.env.HOME = workdir;

type Tools = typeof import("../src/tools.js");
type DdCli = typeof import("../src/ddcli.js");
type Guests = typeof import("../src/guests.js");
type Logger = typeof import("../src/logger.js");
let tools: Tools;
let ddcli: DdCli;
let guests: Guests;
let logger: Logger;

before(async () => {
  chmodSync(FAKE, 0o755);
  tools = await import("../src/tools.js");
  ddcli = await import("../src/ddcli.js");
  guests = await import("../src/guests.js");
  logger = await import("../src/logger.js");
});

after(() => rmSync(workdir, { recursive: true, force: true }));

beforeEach(() => {
  writeFileSync(LOG, "");
  delete process.env.FAKE_DD_CLI_GUEST_SCENARIO;
  guests.forgetCart("cart_1");
  ddcli.resetVersionCache();
  ddcli.invalidateDefaultAddress();
  ddcli.setCallIntent("Help the user order dinner");
});

const GUEST_ADD = {
  cart_uuid: "cart_1",
  guest_first_name: "Alice",
  guest_last_name: "Chen",
  items: [{ item_id: "i_100", item_name: "Tonkotsu Ramen", quantity: 1 }],
};

/** Raw handler output — the exact string the model would receive. */
async function guestAdd(extra: Record<string, unknown> = {}): Promise<string> {
  return tools.toolHandlers.add_items_to_cart({ ...GUEST_ADD, ...extra });
}

/** Everything the audit log has written this run, concatenated. */
function auditLogContents(): string {
  const dir = join(workdir, ".peckish", "logs");
  try {
    return readdirSync(dir)
      .map((f) => readFileSync(join(dir, f), "utf8"))
      .join("\n");
  } catch {
    return "";
  }
}

/**
 * The whole contract, asserted the same way for every scenario: log the result
 * exactly as the dispatchers do, then hunt for the credential in both places.
 */
function assertContained(where: string, result: string): void {
  // The log only ever appends, and one file serves the whole process — so
  // compare the delta, or the first leak would fail every later case too.
  const before = auditLogContents();
  logger.logToolCall("add_items_to_cart", GUEST_ADD, true, 1, result);
  const appended = auditLogContents().slice(before.length);
  assert.equal(result.includes(TOKEN), false, `${where}: token reached the model`);
  assert.equal(appended.includes(TOKEN), false, `${where}: token reached the audit log`);
}

// ---------------------------------------------------------------------------
// The shape the code was written for
// ---------------------------------------------------------------------------

test("happy path: token is stored, and absent from the result", async () => {
  const result = await guestAdd();
  assertContained("nominal", result);

  // Contained AND captured — continuity depends on the store having it.
  assert.equal(guests.guestToken("cart_1", "Alice", "Chen"), TOKEN);
  const parsed = JSON.parse(result);
  assert.equal(parsed.guest, "Alice Chen");
  assert.equal(parsed.guest_add, "new guest");
  assert.equal(parsed.warning, undefined, "nothing was lost, so nothing to warn about");
});

test("a second add for the same guest sends the token back, never the name", async () => {
  await guestAdd();
  writeFileSync(LOG, "");
  const result = await guestAdd();

  const argv: string[] = JSON.parse(readFileSync(LOG, "utf8").split("\n").filter(Boolean)[0]);
  const sent = JSON.parse(argv[argv.indexOf("--guest-json") + 1]);
  assert.deepEqual(sent, { guest_token: TOKEN }, "reuse must send only the token");
  assert.equal(JSON.parse(result).guest_add, "existing guest");
  assertContained("reuse", result);
});

// ---------------------------------------------------------------------------
// Shapes the code was NOT written for
// ---------------------------------------------------------------------------

test("camelCase guestToken is stripped and still captured", async () => {
  process.env.FAKE_DD_CLI_GUEST_SCENARIO = "camel";
  const result = await guestAdd();
  assertContained("camelCase key", result);

  // Both halves normalize the key, so an unexpected spelling costs nothing:
  // the credential is contained AND continuity survives, so no warning is due.
  assert.equal(guests.guestToken("cart_1", "Alice", "Chen"), TOKEN);
  assert.equal(JSON.parse(result).warning, undefined);
});

test("token echoed in free text is scrubbed from the result", async () => {
  process.env.FAKE_DD_CLI_GUEST_SCENARIO = "in_message";
  const result = await guestAdd();
  // Key-based stripping cannot catch a credential pasted into a message field.
  assertContained("echoed in message", result);
  // The correctly-keyed copy still has to be captured.
  assert.equal(guests.guestToken("cart_1", "Alice", "Chen"), TOKEN);
});

test("nesting past the finder's depth cap loses continuity without leaking", async () => {
  process.env.FAKE_DD_CLI_GUEST_SCENARIO = "deep";
  const result = await guestAdd();
  assertContained("deep nesting", result);
  assert.match(JSON.parse(result).warning ?? "", /could not record this guest/i);
});

test("camelCase nested past the depth cap is still contained", async () => {
  process.env.FAKE_DD_CLI_GUEST_SCENARIO = "deep_camel";
  const result = await guestAdd();
  // findGuestToken is depth-capped, so the value is never learned and there is
  // nothing to redact by value. Only the stripper's key normalization — which
  // recurses without a depth limit — stands between this and the model.
  assertContained("camelCase past depth cap", result);
  assert.equal(guests.guestToken("cart_1", "Alice", "Chen"), null);
  assert.match(JSON.parse(result).warning ?? "", /could not record this guest/i);
});

test("a token inside an array is contained and captured", async () => {
  process.env.FAKE_DD_CLI_GUEST_SCENARIO = "array";
  const result = await guestAdd();
  assertContained("array element", result);
  assert.equal(guests.guestToken("cart_1", "Alice", "Chen"), TOKEN);
});

test("a failed add does not leak the token through the error detail", async () => {
  process.env.FAKE_DD_CLI_GUEST_SCENARIO = "error_echo";
  let surfaced: string;
  try {
    surfaced = await guestAdd();
  } catch (err) {
    // This is what the dispatchers put in front of the model on a throw.
    const e = err as { message: string; detail?: string };
    surfaced = JSON.stringify({ error: e.message, detail: e.detail });
  }
  assertContained("error detail", surfaced);
});

// ---------------------------------------------------------------------------
// The store itself
// ---------------------------------------------------------------------------

test("the guest store is not world-readable", async () => {
  await guestAdd();
  const mode = statSync(guests.guestsFilePath()).mode & 0o777;
  assert.equal(mode, 0o600, `guests.json should be 0600, got ${mode.toString(8)}`);
  const dirMode = statSync(join(workdir, ".peckish")).mode & 0o777;
  assert.equal(dirMode & 0o077, 0, `~/.peckish should not be group/world accessible, got ${dirMode.toString(8)}`);
});

test("list_cart_guests exposes names and never tokens", async () => {
  await guestAdd();
  const result = await tools.toolHandlers.list_cart_guests({ cart_uuid: "cart_1" });
  assert.deepEqual(JSON.parse(result).guests, ["Alice Chen"]);
  assertContained("list_cart_guests", result);
});

test("forgetting a cart removes the credential from disk", async () => {
  await guestAdd();
  guests.forgetCart("cart_1");
  assert.equal(guests.guestToken("cart_1", "Alice", "Chen"), null);
  const onDisk = readFileSync(guests.guestsFilePath(), "utf8");
  assert.equal(onDisk.includes(TOKEN), false, "the token must not survive on disk");
});
