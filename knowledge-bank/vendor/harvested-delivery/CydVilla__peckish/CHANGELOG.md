# Changelog

All notable changes to Peckish. Format follows [Keep a Changelog](https://keepachangelog.com);
versions follow semver (0.x: minor = features, patch = fixes). Each release on
[GitHub Releases](https://github.com/CydVilla/peckish/releases) carries this
file's section for that version, every downloadable artifact, and a
`SHA256SUMS.txt` to verify them.

## [0.5.0] - 2026-09-25

### Security
- **Three ways the guest sub-cart token could reach the model, now closed.**
  `guest_token` is a bearer credential dd-cli issues once and cannot reissue,
  and stripping it by key name turned out not to be enough. Adversarial tests
  that make the fake CLI return it in shapes Peckish was not written for found
  that it escaped when: the key was spelled `guestToken` (the stripped-key set
  matched the exact string `guest_token`); the value was echoed inside a
  free-text field, where key-based stripping cannot reach it; or the add failed,
  because `DdCliError.detail` is raw stdout+stderr and reached the model from
  three separate call sites without ever passing through the stripper.
  - Stripped-key matching and `findGuestToken` now compare with case and
    separators removed, so an unexpected spelling is both contained and still
    captured — continuity no longer depends on dd-cli's choice of casing.
  - A new `redactGuestTokens()` removes token assignments from free text and
    redacts known values, applied to the guest-add result and — at the single
    place every call site shares — to `DdCliError.detail`.
  - `tests/guest-token.test.ts` covers all of it: eleven cases driving six
    adversarial response shapes, each asserting the credential appears neither
    in what the handler returns nor in the audit log written from it. Losing
    continuity is an acceptable failure; leaking the credential is not.

### Fixed
- **`submit_order` could never confirm an order it had just placed.** The poll
  read `final_status.status`, but dd-cli nests the order under `result` — there
  is no top-level `status`, and the pre-0.2.3 value `successful` the note and
  tool description told the model to look for no longer exists at all. So the
  loop never saw a non-`pending` value: it burned all 8 attempts (40 seconds) on
  every submit and then handed the model a contract it could not satisfy. Status
  now comes from `result.status` through a derived `lifecycle` block
  (`order_created`, `is_terminal`, `keep_polling`, `not_found`), and the poll
  exits on the first conclusive check. Cart cleanup no longer depends on a
  string comparison that always failed through to `submitRes.success`.
- **Order history rows came back undated.** The mapper read `created_at`, which
  dd-cli does not return; the real fields are `order_date` and
  `order_fulfilled_at`. Item `item_id` was dropped too. Rows carry no total and
  no per-item price on 0.2.5, so the tool description stops promising them and
  points at `get_receipt` instead.
- **Peckish told the model "no popularity data exists" while discarding it.**
  Menu items carry `is_popular`, `popularity_rank` and `popular_modifications`.
  The tokens now carry them through and the instruction says to use them.
- **Verified against a real dd-cli 0.2.5, and two menu fields were being
  dropped.** The 0.2.3–0.2.5 catch-up was written from release notes, which
  name features but not response fields; `menu --help` on the real binary names
  them. Two fell through both the explicit trimmer picks and
  `CARRY_THROUGH_TOKENS`:
  - `items[].orderability` (the per-item `asap` / `schedule_ahead` list) — no
    token matched it, so the model never saw it *while `get_menu`'s own
    description promised it was there*. Added as its own token.
  - `store_next_open_time` — now picked explicitly next to `store_is_open`,
    rather than widening the token set with "open"/"time" and dragging
    unrelated timestamps through every menu.

  Both were then confirmed present in live responses, along with every flag:
  `verify-dd-cli.mjs` reports 17 passed, 0 failed against a signed-in 0.2.5.
  `promotions[]` and `applicable_promotion_ids` are matched by the existing
  tokens, the 0.2.5 pickup fields were already allowlisted by name, and
  `findGuestToken()` searches by key name rather than path — 0.2.5 confirms the
  key is exactly `guest_token` on the acted-for subcart.
- `tests/fixtures/fake-dd-cli.mjs` now mirrors real observed responses: the
  `order status` envelope nested under `result`, ISO `order_date` /
  `order_fulfilled_at` on history rows, and item popularity. Its invented flat
  `{status: "successful"}` is why the broken poll passed tests for so long.
  `submit_order` had no test coverage at all and now does.
- The fixture also uses the field names the real CLI documents (`applicable_promotion_ids`, `orderability`, `supports_order_ahead`,
  `promotions[].code`) instead of invented ones. The invented names happened to
  match the token set, which is why the suite stayed green while `orderability`
  was being dropped.

### Added
- **Guest sub-carts.** A group cart can now hold items for people with no
  DoorDash account: `add_items_to_cart` takes `guest_first_name` +
  `guest_last_name` and puts that person's items in their own sub-cart of a
  group cart the signed-in user hosts. `list_cart_guests` shows who is being
  tracked. This was the last substantial dd-cli capability Peckish did not
  reach — it is what lets one person with the CLI order for a team where
  nobody else has an account.
  - **The per-guest token never reaches the model.** DoorDash returns a
    `guest_token` on a guest's first add; it is a bearer credential for their
    sub-cart, appears exactly once (`cart show` never echoes it, nothing can
    fetch it again), and dd-cli's guidance is to keep it out of logs and away
    from humans. Peckish stores it in `~/.peckish/guests.json` (mode `0600`)
    keyed by cart and guest name, and `guest_token` is now stripped from every
    tool result — so it also never lands in the session audit log, which
    previews every result. The model refers to guests by name only and has no
    way to read or supply a token.
  - Peckish enforces dd-cli's constraints itself rather than letting a bad
    call fail downstream: a guest add needs an existing cart, cannot carry
    `group_cart`/`spend_limit_cents`, needs both halves of the name, and never
    sends a name alongside a token.
  - A cart's guests are dropped when its order is submitted or the cart is
    deleted; entries older than 30 days are pruned on write.
- **Joining a group cart now uses its link.** `add_items_to_cart` takes
  `group_cart_url`, which is how dd-cli actually joins another person's group
  cart — the previous guidance (their `cart_uuid` plus `group_cart`) described
  creating a cart, not joining one.
- Both system prompts now spell out that cart adds are **additive, not
  idempotent**: after a timeout or error, check `item_errors[]` before
  retrying, because an item missing from that list already went in and a retry
  doubles it.

### Added
- **End-to-end tests for the dd-cli command line Peckish builds.** A fake
  dd-cli (`tests/fixtures/fake-dd-cli.mjs`) records the argv each handler
  produces and answers with realistic envelopes, so the tests assert what
  Peckish actually sends — that `--address-id` replaces `--lat/--lng` on a
  0.2.4+ binary and not before, that `--price-tier` repeats per tier, that an
  unsupported command is never attempted, that decimal weights and
  `default_handling` survive serialization, and that every consumer command
  still carries `--json-output` and `--intent`. It cannot confirm dd-cli's
  real flag names — only a live binary can — but it covers the half Peckish
  owns. 19 new cases; the suite is 56.
- **`scripts/verify-dd-cli.mjs`** — run Peckish's assumptions against a real,
  signed-in dd-cli. Read-only (no carts, addresses, promos or orders): it
  reports which flags the installed binary accepts and prints the field names
  the responses actually carry, so the promo/order-ahead/weight key patterns
  in `src/tools.ts` can be replaced with certainty.
- **`docs/dd-cli-verification.md`** — the checklist for acting on what
  `verify-dd-cli.mjs` reports: which flag names to correct and where, how to
  reconcile the real response field names against the trimmers' token set, and
  which two write paths stay unexercised without explicit consent.
- **`scripts/check-dd-cli-release.mjs` and a weekly release-watch workflow.**
  Peckish sat three dd-cli releases behind before anyone noticed; this checks
  the published releases against `DD_CLI_RECOMMENDED_VERSION` every Monday and
  files an issue when a newer one is out.

### Fixed
- The age-restriction path is now named rather than implied: both system
  prompts call out `error_reason AGENTIC_RESTRICTED_ITEM_NOT_ALLOWED` on
  `submit_order` as the signal to hand over `get_checkout_url` instead of
  retrying the submit.

### Added
- **dd-cli 0.2.3–0.2.5 support.** Peckish had been built against dd-cli 0.2.2;
  three releases of new surface went unused. Now wired through:
  - **Address lookup** (dd-cli 0.2.3): `find_address` resolves a typed address
    to candidates and `add_address` saves the chosen one. Saving also makes it
    the account-wide default, so it sits behind the same approval prompt as
    `set_default_address`.
  - **Group orders in history** (0.2.3): `get_order_history` takes
    `include_group_order`, and group fields survive the response trim — team
    and office orders were invisible before.
  - **Full order lifecycle** (0.2.3): `get_order_status` now documents what it
    actually returns — placement and delivery progress, current ETA, late
    trend, actual delivery time, cancellation reason — so "where's my food?"
    is answered from the CLI rather than inferred from the submit response.
  - **Promo-aware menus** (0.2.4): `get_menu` and `get_restaurant_item_details`
    pass `--address-id`, so the store's active promotions and the items that
    qualify come back priced against the right delivery location.
  - **Search from a saved address** (0.2.4): `search_restaurants` and
    `find_stores` take `address_id`. Searching by coordinates alone dropped
    the promo context; the saved address id is now preferred whenever the
    installed dd-cli supports it.
  - **Search filters** (0.2.5): `dashpass_only`, `price_tier`,
    `distance_preference` and `max_eta_minutes` narrow server-side instead of
    over-fetching and filtering in the prompt.
  - **Pickup availability and schedule-ahead** (0.2.5): search results carry
    `offers_pickup`, `asap_pickup_availability`,
    `scheduled_pickup_availability` and `next_open_time_asap_pickup_ms`, and
    order-ahead windows now reach the model — a store that is closed now gets
    offered as a scheduled order instead of being dropped.
  - **Weight-priced items and merchant defaults** (0.2.5): cart items take a
    decimal `quantity` with a `unit`, and `default_handling: "exact"` opts out
    of a merchant's default modifications. The strict tool schemas had made
    both literally inexpressible.
- **dd-cli version detection.** Peckish probes `dd-cli --version` once per
  process, reports it in the session context, and gates the behaviours it
  applies automatically (like pricing menus against your saved address) on a
  confirmed version — so a newer Peckish keeps working on an older binary
  instead of failing on an unknown flag. Flags asked for explicitly are still
  passed through, so dd-cli's own error names the flag.
- **Response fields added after this code was written now survive the trim.**
  The menu/search trimmers were strict allowlists, which silently swallowed
  every field dd-cli added; keys naming a promotion, discount, order-ahead
  window or weight/unit now ride along.
- **Linux (x86_64) support**, following dd-cli v0.2.2's Linux builds. The
  terminal, web and MCP surfaces all run on Linux — same tools, same order
  gate, same audit log. dd-cli is discovered at `~/.local/bin/dd-cli`,
  `/usr/local/bin/dd-cli`, `DD_CLI_PATH`, or `PATH`. (The `.dmg` remains the
  one Mac-only surface.)
- **Browserless sign-in** for containers, VMs and cloud sandboxes: where
  `dd-cli login` can't complete, Peckish stops offering it — no spawned login
  that hangs, no advice that can't work — and tells you to mint a token with
  `dd-cli export-token` on a machine with a browser and pass it in as
  `DD_CLI_ACCESS_TOKEN`. The agent gets the same guidance on every surface, and
  a set-but-rejected token is reported as stale rather than missing.
- Unsupported platforms (Intel Macs, Linux arm64) now say so — "no dd-cli
  build" — instead of failing with an obscure missing-binary error.
- **Sign-in assist**: when DoorDash sign-in is missing or expired, Peckish now
  offers to fix it instead of sending you to a terminal. The terminal app asks
  before launching `dd-cli login` (which opens your browser) and waits for it;
  the web app serves a sign-in card instead of refusing to boot; and a new
  `start_signin` tool lets the agent offer the same assist mid-conversation on
  every surface — always behind an explicit approval prompt, and it never
  opens a second sign-in window while one is pending.

### Changed
- The Claude Desktop extension now declares `["darwin", "linux"]` compatibility
  (dd-cli ships builds for both), and its docs no longer claim a Mac is
  required.

### Fixed
- The extension manifest's version is now read from `extension/package.json`
  and its tool list from the repo's own build (previously a hardcoded version
  and the installed npm package could both drift).

## [0.4.0] - 2026-07-28

Compatibility release for **dd-cli v0.2.1** (required — older dd-cli versions
no longer work with Peckish 0.4.0, and vice versa). After upgrading dd-cli,
run `dd-cli login` again: new CLI versions can require fresh sign-in scopes.

### Added
- **Group carts**: "start a group order, $25 each" — creates a shareable cart
  link (`group_cart_url`), optional per-person spend limit, join someone
  else's cart by its id; the host previews and submits.
- **Priority (express) delivery**: request the paid faster option; Peckish
  verifies the cart actually offers it before promising, and carries the same
  choice through to submit so the charge matches the quote.
- **Credits control**: DoorDash credits apply by default; "don't use my
  credits" opts a single order out (preview and submit stay consistent).
- **Enterprise chains**: Domino's, Sweetgreen, Dave's Hot Chicken and other
  large chains are now orderable.
- Dockerfile for registry/CI introspection (the MCP server boots and lists
  its tools without dd-cli, which is only executed at tool-call time).

### Changed
- Every dd-cli call now carries the CLI's new required `--intent` note —
  with a **privacy-preserving default**: Peckish sends a generic goal summary
  and explicitly withholds your verbatim prompt unless you set
  `PECKISH_INTENT_VERBATIM=1`. See README → "What Peckish shares with
  DoorDash".
- Preview results now include the cart's delivery options (so express
  availability is visible to the agent).

### Fixed
- dd-cli v0.2.1's new authentication-failure message is recognized and
  surfaced as a clear "run `dd-cli login`" instruction instead of a generic
  error.

## [0.3.0] - 2026-07-23

### Added
- Rotating suggestion prompts on the web app's start screen.

### Changed
- Coordinated version bump across all packages (`peckish`, `peckish-mcp`,
  desktop, extension) with dependency ranges moved to `^0.3.0`.

## [0.2.2] - 2026-07-21

### Added
- `peckish-mcp` npm package — one-line MCP install:
  `claude mcp add peckish -- npx -y peckish-mcp`.
- Listed in the official MCP Registry as `io.github.CydVilla/peckish`.
- Claude Desktop `.mcpb` bundle (double-click install) attached to releases.

## [0.2.1] - 2026-07-21

### Added
- Address switcher in the web app: click the address chip to change your
  default delivery address (text edits happen on doordash.com; Peckish picks
  them up automatically).

## [0.2.0] - 2026-07-21

First public release.

### Added
- Three surfaces over one tool layer: terminal chat (`peckish`), local web
  app (`peckish-web`), and MCP server for Claude Desktop / Claude Code.
- Full ordering flow on DoorDash's official dd-cli: search, menus and
  customizations, carts, real fee-included quotes, promos, reorders, order
  history and receipts, groceries/retail, work benefits, scheduled delivery.
- Safety model: placing an order always requires an explicit human approval
  rendered by the surface (typed `yes` / web modal / MCP elicitation dialog,
  fail closed); tip confirmed and payment card named before any submit ask;
  submissions never auto-retry; JSONL audit log of every tool call.
- Cost-lean defaults: claude-sonnet-5 at medium effort, prompt caching,
  per-session cost meter.
- Mac app (.dmg) with guided no-terminal setup.
