# Verifying Peckish against a real dd-cli

Peckish's support for dd-cli 0.2.3–0.2.5 was implemented from the published
release notes, in an environment with no dd-cli binary available. It is unit-
and integration-tested against a fake CLI (`tests/fixtures/fake-dd-cli.mjs`),
which proves Peckish sends what it claims to send — but a fake cannot tell us
what the real binary *accepts*, or what its responses are really called.

This is the checklist for closing that gap on a machine that has dd-cli
installed and signed in. Run `dd-cli --version` first; if that fails, nothing
below applies.

## 1. Run the script

```sh
node scripts/verify-dd-cli.mjs
node scripts/verify-dd-cli.mjs --store-id <id>   # if search finds nothing usable
```

Read-only: lookups only, no carts, no saved addresses, no promos, no orders.
`address add` is deliberately excluded because it mutates the account. It needs
at least one saved address.

Keep the whole output — both the PASS/FAIL lines and the key lists
(`all store keys:`, `top-level menu keys:`, `sample item keys:`,
`status keys:`).

## 2. Fix any FAIL

A FAIL means Peckish sends a flag this dd-cli doesn't accept. The names came
from release notes and may be wrong. Check `dd-cli <command> --help`, then fix
**both** places in `src/tools.ts`:

- the handler in `toolHandlers` that builds the argv
- the matching entry in `RAW_TOOLS` — the strict JSON schema

A flag the schema can't express is a flag the model can't use, so the two
always change together. Then update the matching assertion in
`tests/integration.test.ts`.

Flags to check, by release:

| Release | Flags |
|---|---|
| 0.2.3 | `address find --query`, `order history --include-group-order` |
| 0.2.4 | `--address-id` on `search`, `find-nearby-stores`, `menu`, `restaurant-item-details` |
| 0.2.5 | `--dashpass-only`, `--price-tier` (repeatable, 1–4), `--distance-preference` (nearby/balanced/broad), `--max-eta-minutes` |

## 3. The important part — real field names

`src/tools.ts` carries new response fields through the menu and search trimmers
by matching key *names* against `CARRY_THROUGH_TOKENS`, because the 0.2.4
release notes say menus surface "a store's active promotions and which items
qualify" without ever naming the fields. That is a guess, and it is the one
thing in the dd-cli catch-up that a live run can settle.

Compare the key lists the script printed against `CARRY_THROUGH_TOKENS`:

- A real promo / order-ahead / schedule-ahead / weight-pricing key that the
  token set does **not** match is being silently dropped before the model sees
  it. Add its token.
- If the token set is pulling through large noisy fields that aren't signal,
  tighten it — menus run to thousands of items and the context is finite.

Two known limits of `carriesSignal()`: it matches whole snake_case tokens, not
substrings (so `community_rating` doesn't qualify via "unit"), and it does not
handle camelCase. If dd-cli returns camelCase keys anywhere, that function
needs to split on case boundaries too.

Finally, update `tests/fixtures/fake-dd-cli.mjs` to use the field names and
shapes you actually observed, so the integration tests test reality rather than
an invented schema.

## 4. Write paths — only with explicit consent

Everything above is read-only. Two paths remain unexercised because they change
real account state:

- `address add --place-id` — saves an address **and** makes it the account-wide
  default
- a weight-priced `cart add-items` with a decimal quantity
- a guest add (`cart add-items --guest-json`) — creates a real sub-cart in a
  real group cart. Worth dry-running per the `dd-group-cart-slackbot` skill's
  own procedure (create a group cart with a tiny `--spend-limit-cents`, add a
  guest, add a second item for the same guest, confirm `cart show` never
  echoes the token, then `cart delete` — never `order submit`). If dd-cli
  returns the `guest_token` somewhere other than where `findGuestToken()`
  looks, Peckish will warn on the add and lose that guest's continuity, so
  confirm the token is captured by checking `~/.peckish/guests.json`

Don't run either unless the user asks for it. Delete any test cart afterwards.

## Done

`npm run typecheck && npm test` green, `verify-dd-cli.mjs` reporting no FAILs,
and a commit describing what the real binary turned out to do differently.

If everything passes unchanged, that is a real result too — record it in the
CHANGELOG's Unreleased section so the next person doesn't repeat the work.
