# Capture-fixture replay provider runbook (F5.AC3)

`CaptureFixtureProvider` replays **sanitized** capture fixtures so that
adapter authors and tests can reason about a captured provider's traffic
shape without re-issuing requests against the live site. It is the F5.AC3
counterpart to the F5.AC1 importer (`vessel-capture-import`) and the
F5/F5A.AC2 capture workflow.

The provider is **opt-in only**. The default `createProviderRegistry()`
still returns the deterministic `FixtureProvider` defined for F2.AC3; the
capture-fixture provider is never auto-loaded.

## Hard rules

- The provider refuses to construct unless every loaded fixture carries
  `provenance.liveReplayDisabled === true`. Fixtures without provenance,
  with a different value, or with an unsupported `version` are rejected
  at construction time with a `CaptureFixtureProviderError`.
- The provider declares `accessClass: 'capture-fixture'` and
  `tier: 'capture-fixture'`. The router (`src/providers/router.ts`)
  excludes this tier under the default `allow-terrestrial` and the
  `strict` fallback policies, and only includes it when the caller opts
  in with `fallbackPolicy: 'allow-fixture'` or an explicit
  `preferredProviderId`/`credentialProfile.providerId` that points at the
  capture-fixture provider.
- `credentialRequirement()` returns `{ required: false, mode: 'none' }`.
  The provider does not accept credentials and never calls the captured
  site. This keeps the adapter inert against the source provider.
- Decoders are **caller-supplied**. The default decoder is `noOpDecoder`,
  which returns nothing. Without a project-specific decoder, every query
  capability returns a structured `NoDataResult`. Provider-specific
  decoders are F4 adapter work, not F5.AC3.

## Producing fixtures

1. Import a HAR or JSON sample with the F5.AC1 CLI:
   `npx vessel-capture-import --in path/to/raw.har --label <provider>`.
2. For an end-to-end run (mock driver by default), use the F5A.AC2
   workflow CLI: `npm run capture:run -- --profile <profile.json> ...`.
   The workflow stamps
   `fixture.provenance = { liveReplayDisabled: true, ... }` automatically.
3. The sanitized fixture file is the only input to the replay provider.
   Raw HAR files, `.env`, cookies, and `captures/raw/` artifacts stay
   gitignored and must never be passed to the provider.

## Loading the provider

```ts
import { readFileSync } from 'node:fs';
import { createCaptureFixtureProvider } from 'vessel-traffic-mcp/dist/providers/capture-fixture.js';
import { createProviderRegistry } from 'vessel-traffic-mcp/dist/providers/registry.js';

const fixture = JSON.parse(readFileSync('fixtures/captures/marinetraffic-search.fixture.json', 'utf8'));

const captureProvider = createCaptureFixtureProvider({
  fixtures: [fixture],
  // omit `decoder` to use the no-op decoder (returns no_data for every query).
  // Supply a project-specific decoder to translate sanitized entries into
  // VesselIdentity / VesselPosition / VesselTrackPoint / PortCall records.
});

// Opt-in registry that includes the capture-fixture provider alongside
// any other providers the caller wants exercised in dev/tests.
const registry = createProviderRegistry([captureProvider]);
```

The default registry continues to behave as before:
`createProviderRegistry().providers().map(p => p.id) === ['fixture']`.

## Routing semantics

The router treats `capture-fixture` as a lowest-priority tier, below
`paid-commercial` and only above the local `fixture` tier. The
intentional consequence is:

- `fallbackPolicy: 'allow-terrestrial'` (default) → `capture-fixture`
  is skipped with `skippedReason: 'fallback_policy_excludes_capture'`.
- `fallbackPolicy: 'strict'` → skipped.
- `fallbackPolicy: 'allow-fixture'` → considered. Useful for adapter
  development and integration tests, never for production traffic.
- Explicit `preferredProviderId` or matching `credentialProfile` →
  treated as `requested-byok` for ranking but the
  `'fallback_policy_excludes_capture'` skip still applies unless the
  policy is `allow-fixture` or the request explicitly opts in.

This means: leaving the default policy alone is enough to prevent
capture-fixture replay from leaking into live MCP responses, even if an
operator forgets to remove the provider from the registry.

## Decoder contract

```ts
interface CaptureFixtureDecoder {
  readonly id: string;
  matchesEntry?(entry: FixtureEntry, fixture: CaptureFixture): boolean;
  decodeIdentities?(entry, fixture): readonly VesselIdentity[];
  decodePositions?(entry, fixture): readonly VesselPosition[];
  decodeTrackPoints?(entry, fixture): readonly { identity, points }[];
  decodePortCalls?(entry, fixture): readonly PortCall[];
}
```

Notes:

- Decoders must be **pure functions of the sanitized fixture entry**.
  Never read environment variables, never make network calls, never
  reach into credential profiles — the provider never feeds those in.
- Decoders must tolerate `[REDACTED]` values. The AC1 importer
  intentionally replaces sensitive header values, cookies, query params,
  and JSON body fields with that placeholder. A decoder that throws or
  panics on `[REDACTED]` will be rejected during adapter review.
- Per-provider decoders belong with the provider adapter (F4), not in
  this module. `noOpDecoder` is what the F5.AC3 acceptance criterion
  ships; it is correct for "F5.AC3 closed, F4 decoder still pending".

## Test verification

`test/provider-capture-fixture.test.js` exercises:

- Default registry remains fixture-only (capture-fixture is opt-in).
- Construction guard rejects missing provenance, wrong version, and
  `liveReplayDisabled !== true`.
- `noOpDecoder` returns structured `NoDataResult`s for every query
  capability.
- A maritime-example decoder produces deterministic, redacted-safe
  search, position, area, and track results from a HAR imported through
  the AC1 redactor.
- Routing default (`allow-terrestrial`) excludes capture-fixture;
  `allow-fixture` includes it.

Run with `npm test`. The default verification path never calls a live
provider.
