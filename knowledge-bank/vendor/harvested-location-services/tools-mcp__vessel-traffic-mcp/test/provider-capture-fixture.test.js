import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  CAPTURE_FIXTURE_ADAPTER_VERSION,
  CaptureFixtureProvider,
  CaptureFixtureProviderError,
  createCaptureFixtureProvider,
  noOpDecoder,
} from '../dist/providers/capture-fixture.js';
import { importCapture, FIXTURE_FORMAT_VERSION } from '../dist/capture/import.js';
import { createProviderRegistry } from '../dist/providers/registry.js';
import { routeProvider } from '../dist/providers/router.js';
import { isDataResult, isNoDataResult } from '../dist/providers/types.js';

const FIXTURE_NOW = '2026-05-15T12:00:00.000Z';

const HAR_INPUT = JSON.stringify({
  log: {
    version: '1.2',
    creator: { name: 'capture-fixture-tests', version: '1.0' },
    entries: [
      {
        startedDateTime: '2026-05-14T10:00:00.000Z',
        request: {
          method: 'GET',
          url: 'https://api.maritime.example.test/v1/vessels?mmsi=477806100&api_key=secret-token',
          headers: [
            { name: 'Authorization', value: 'Bearer should-be-redacted' },
            { name: 'Accept', value: 'application/json' },
          ],
          cookies: [{ name: 'session', value: 'should-be-redacted' }],
        },
        response: {
          status: 200,
          statusText: 'OK',
          headers: [{ name: 'Content-Type', value: 'application/json' }],
          cookies: [],
          content: {
            mimeType: 'application/json',
            text: JSON.stringify({
              vessels: [
                {
                  mmsi: '477806100',
                  imo: '9839272',
                  name: 'EVER GIVEN',
                  callsign: 'H3RC',
                  position: {
                    lat: 30.5852,
                    lon: 32.2654,
                    speedKnots: 12.3,
                    courseDeg: 45,
                    observedAt: '2026-05-14T09:59:30.000Z',
                  },
                },
              ],
            }),
          },
        },
      },
      {
        startedDateTime: '2026-05-14T10:01:00.000Z',
        request: {
          method: 'GET',
          url: 'https://api.maritime.example.test/v1/vessels?mmsi=538009132',
          headers: [{ name: 'Accept', value: 'application/json' }],
          cookies: [],
        },
        response: {
          status: 200,
          statusText: 'OK',
          headers: [{ name: 'Content-Type', value: 'application/json' }],
          cookies: [],
          content: {
            mimeType: 'application/json',
            text: JSON.stringify({
              vessels: [
                {
                  mmsi: '538009132',
                  imo: '9778888',
                  name: 'PACIFIC CARRIER',
                  callsign: 'V7AB1',
                  position: {
                    lat: 1.35,
                    lon: 103.85,
                    speedKnots: 9.5,
                    courseDeg: 90,
                    observedAt: '2026-05-14T10:00:50.000Z',
                  },
                },
              ],
            }),
          },
        },
      },
    ],
  },
});

function sanitizedFixtureWithProvenance() {
  const { fixture } = importCapture(HAR_INPUT, {
    format: 'har',
    label: 'capture-fixture-replay-test',
    source: 'test:in-memory-har',
    now: () => '2026-05-14T10:02:00.000Z',
  });
  return {
    ...fixture,
    provenance: {
      siteProfileId: 'maritime-test.example',
      siteProfileVersion: 1,
      recorderDriver: 'mock',
      liveReplayDisabled: true,
      capturedAt: '2026-05-14T10:02:00.000Z',
      notes: ['test-only fixture; never replayable as a live session'],
    },
  };
}

function maritimeExampleDecoder() {
  return {
    id: 'maritime-example-v1',
    matchesEntry(entry) {
      return entry.method === 'GET' && entry.url.includes('/v1/vessels');
    },
    decodeIdentities(entry) {
      const vessels = parseVessels(entry);
      return vessels.map((v) => ({
        mmsi: v.mmsi,
        imo: v.imo,
        name: v.name,
        callsign: v.callsign,
      }));
    },
    decodePositions(entry) {
      const vessels = parseVessels(entry);
      return vessels
        .filter((v) => v.position)
        .map((v) => ({
          identity: { mmsi: v.mmsi, imo: v.imo, name: v.name, callsign: v.callsign },
          lat: v.position.lat,
          lon: v.position.lon,
          speedKnots: v.position.speedKnots,
          courseDeg: v.position.courseDeg,
          observedAt: v.position.observedAt,
          retrievedAt: entry.startedAt ?? FIXTURE_NOW,
          freshnessSeconds: 30,
          source: {
            provider: 'capture-fixture',
            adapterVersion: CAPTURE_FIXTURE_ADAPTER_VERSION,
            transport: 'capture-fixture',
          },
        }));
    },
    decodeTrackPoints(entry) {
      const vessels = parseVessels(entry);
      return vessels
        .filter((v) => v.position)
        .map((v) => ({
          identity: { mmsi: v.mmsi, imo: v.imo, name: v.name },
          points: [
            {
              lat: v.position.lat,
              lon: v.position.lon,
              observedAt: v.position.observedAt,
              speedKnots: v.position.speedKnots,
              courseDeg: v.position.courseDeg,
            },
          ],
        }));
    },
    decodePortCalls() {
      return [];
    },
  };
}

function parseVessels(entry) {
  if (!entry.response.body) return [];
  try {
    const body = JSON.parse(entry.response.body);
    return Array.isArray(body.vessels) ? body.vessels : [];
  } catch {
    return [];
  }
}

test('CAPTURE_FIXTURE_ADAPTER_VERSION is a stable string', () => {
  assert.equal(typeof CAPTURE_FIXTURE_ADAPTER_VERSION, 'string');
  assert.ok(CAPTURE_FIXTURE_ADAPTER_VERSION.startsWith('capture-fixture-'));
});

test('default createProviderRegistry remains fixture-only and does NOT include capture-fixture', () => {
  const registry = createProviderRegistry();
  const ids = registry.providers().map((p) => p.id);
  assert.deepEqual(ids, ['fixture'], 'opt-in only — capture-fixture must not appear in the default registry');
});

test('CaptureFixtureProvider throws when no fixtures are supplied', () => {
  assert.throws(
    () => createCaptureFixtureProvider({ fixtures: [] }),
    (err) => err instanceof CaptureFixtureProviderError && /at least one sanitized fixture/.test(err.message),
  );
});

test('CaptureFixtureProvider throws when a fixture lacks provenance', () => {
  const { fixture } = importCapture(HAR_INPUT, { format: 'har', label: 'no-provenance', now: () => FIXTURE_NOW });
  // No provenance is attached on purpose; provider must refuse to load it.
  assert.throws(
    () => createCaptureFixtureProvider({ fixtures: [fixture] }),
    (err) =>
      err instanceof CaptureFixtureProviderError &&
      /missing provenance|liveReplayDisabled/.test(err.message),
  );
});

test('CaptureFixtureProvider throws when provenance.liveReplayDisabled !== true', () => {
  const fixture = sanitizedFixtureWithProvenance();
  const tampered = {
    ...fixture,
    provenance: { ...fixture.provenance, liveReplayDisabled: false },
  };
  assert.throws(
    () => createCaptureFixtureProvider({ fixtures: [tampered] }),
    (err) => err instanceof CaptureFixtureProviderError && /liveReplayDisabled !== true/.test(err.message),
  );
});

test('CaptureFixtureProvider throws when fixture declares unsupported version', () => {
  const fixture = { ...sanitizedFixtureWithProvenance(), version: 99 };
  assert.throws(
    () => createCaptureFixtureProvider({ fixtures: [fixture] }),
    (err) => err instanceof CaptureFixtureProviderError && /unsupported version 99/.test(err.message),
  );
});

test('capture-fixture default decoder is the no-op decoder', () => {
  const provider = createCaptureFixtureProvider({
    fixtures: [sanitizedFixtureWithProvenance()],
    now: () => FIXTURE_NOW,
  });
  assert.equal(provider.decoderId(), 'no-op');
  assert.equal(noOpDecoder.id, 'no-op');
});

test('capture-fixture provider with no-op decoder returns no_data for every query capability', async () => {
  const provider = createCaptureFixtureProvider({
    fixtures: [sanitizedFixtureWithProvenance()],
    now: () => FIXTURE_NOW,
  });
  const search = await provider.search({ mmsi: '477806100' });
  assert.ok(isNoDataResult(search));
  assert.equal(search.reason, 'identifier_not_found');
  assert.match(search.message, /no-op|no project-specific decoder/);

  const position = await provider.latestPosition({ mmsi: '477806100' });
  assert.ok(isNoDataResult(position));
  assert.equal(position.reason, 'identifier_not_found');

  const area = await provider.area({
    boundingBox: { latMin: -90, latMax: 90, lonMin: -180, lonMax: 180 },
  });
  assert.ok(isNoDataResult(area));
  assert.equal(area.reason, 'no_coverage');

  const track = await provider.track({ mmsi: '477806100' });
  assert.ok(isNoDataResult(track));
  assert.equal(track.reason, 'identifier_not_found');

  const portCalls = await provider.portCalls({ mmsi: '477806100' });
  assert.ok(isNoDataResult(portCalls));
  assert.equal(portCalls.reason, 'identifier_not_found');
});

test('capture-fixture metadata declares capture-fixture tier and accessClass', () => {
  const provider = createCaptureFixtureProvider({
    fixtures: [sanitizedFixtureWithProvenance()],
    now: () => FIXTURE_NOW,
  });
  const metadata = provider.metadata();
  assert.equal(metadata.accessClass, 'capture-fixture');
  assert.equal(metadata.tier, 'capture-fixture');
  assert.ok(metadata.notes && /opt-in|disabled/i.test(metadata.notes));
});

test('capture-fixture status returns capture-fixture transport and inert quota', async () => {
  const provider = createCaptureFixtureProvider({
    fixtures: [sanitizedFixtureWithProvenance()],
    now: () => FIXTURE_NOW,
  });
  const status = await provider.status();
  assert.equal(status.status, 'available');
  assert.equal(status.authState, 'not_required');
  assert.equal(status.retrievedAt, FIXTURE_NOW);
  assert.equal(status.source.transport, 'capture-fixture');
  assert.equal(status.source.adapterVersion, CAPTURE_FIXTURE_ADAPTER_VERSION);
  assert.equal(status.quota?.state, 'not_applicable');
  assert.ok(status.caveats.some((c) => c.includes('capture-fixture-replay-test')));
});

test('capture-fixture dataSources advertises capture-fixture transport without auth', async () => {
  const provider = createCaptureFixtureProvider({
    fixtures: [sanitizedFixtureWithProvenance()],
    now: () => FIXTURE_NOW,
  });
  const sources = await provider.dataSources();
  assert.equal(sources.length, 1);
  assert.equal(sources[0].transport, 'capture-fixture');
  assert.equal(sources[0].auth.required, false);
  assert.equal(sources[0].auth.mode, 'none');
});

test('capture-fixture credentialRequirement explicitly accepts no credentials', () => {
  const provider = createCaptureFixtureProvider({
    fixtures: [sanitizedFixtureWithProvenance()],
    now: () => FIXTURE_NOW,
  });
  const requirement = provider.credentialRequirement();
  assert.equal(requirement.required, false);
  assert.equal(requirement.mode, 'none');
  assert.deepEqual(requirement.profileFields, []);
});

test('decoded search returns deterministic identity matches across repeated calls', async () => {
  const fixture = sanitizedFixtureWithProvenance();
  const provider = createCaptureFixtureProvider({
    fixtures: [fixture],
    decoder: maritimeExampleDecoder(),
    now: () => FIXTURE_NOW,
  });
  const a = await provider.search({ name: 'ever' });
  const b = await provider.search({ name: 'ever' });
  assert.ok(isDataResult(a));
  assert.deepEqual(a, b);
  assert.equal(a.data.matches[0].mmsi, '477806100');
  assert.equal(a.data.total, 1);
  assert.equal(a.source.transport, 'capture-fixture');
  assert.equal(a.retrievedAt, FIXTURE_NOW);
});

test('decoded latestPosition returns the most-recent observation for the requested mmsi', async () => {
  const provider = createCaptureFixtureProvider({
    fixtures: [sanitizedFixtureWithProvenance()],
    decoder: maritimeExampleDecoder(),
    now: () => FIXTURE_NOW,
  });
  const result = await provider.latestPosition({ mmsi: '477806100' });
  assert.ok(isDataResult(result));
  assert.equal(result.data.identity.mmsi, '477806100');
  assert.equal(result.data.lat, 30.5852);
  assert.equal(result.data.lon, 32.2654);
  assert.equal(result.data.observedAt, '2026-05-14T09:59:30.000Z');
  assert.equal(result.data.source.transport, 'capture-fixture');
  // Position retrievedAt is provided by the decoder, not the provider clock.
  assert.equal(result.retrievedAt, '2026-05-14T10:00:00.000Z');
});

test('decoded area query restricts to the bounding box', async () => {
  const provider = createCaptureFixtureProvider({
    fixtures: [sanitizedFixtureWithProvenance()],
    decoder: maritimeExampleDecoder(),
    now: () => FIXTURE_NOW,
  });
  const insideSuez = await provider.area({
    boundingBox: { latMin: 29, latMax: 31, lonMin: 31, lonMax: 33 },
  });
  assert.ok(isDataResult(insideSuez));
  assert.equal(insideSuez.data.positions.length, 1);
  assert.equal(insideSuez.data.positions[0].identity.mmsi, '477806100');

  const empty = await provider.area({
    boundingBox: { latMin: -80, latMax: -70, lonMin: -180, lonMax: -170 },
  });
  assert.ok(isNoDataResult(empty));
  assert.equal(empty.reason, 'no_coverage');
});

test('decoded track query restricts to the requested time window', async () => {
  const provider = createCaptureFixtureProvider({
    fixtures: [sanitizedFixtureWithProvenance()],
    decoder: maritimeExampleDecoder(),
    now: () => FIXTURE_NOW,
  });
  const result = await provider.track({
    mmsi: '477806100',
    windowStart: '2026-05-14T09:00:00.000Z',
    windowEnd: '2026-05-14T11:00:00.000Z',
  });
  assert.ok(isDataResult(result));
  assert.equal(result.data.points.length, 1);
  assert.equal(result.data.points[0].lat, 30.5852);

  const outside = await provider.track({
    mmsi: '477806100',
    windowStart: '2024-01-01T00:00:00.000Z',
    windowEnd: '2024-01-02T00:00:00.000Z',
  });
  assert.ok(isNoDataResult(outside));
  assert.equal(outside.reason, 'no_recent_position');
});

test('capture-fixture provider does not embed raw secrets from the captured HAR', async () => {
  const provider = createCaptureFixtureProvider({
    fixtures: [sanitizedFixtureWithProvenance()],
    decoder: maritimeExampleDecoder(),
    now: () => FIXTURE_NOW,
  });
  const fixtures = provider.fixtures();
  const serialized = JSON.stringify(fixtures);
  // The AC1 importer is responsible for redaction; we assert here that the
  // capture-fixture provider does not regenerate or surface the secrets.
  assert.ok(!serialized.includes('Bearer should-be-redacted'));
  assert.ok(!serialized.includes('secret-token'));
  assert.ok(serialized.includes('[REDACTED]'));

  const status = await provider.status();
  assert.ok(!JSON.stringify(status).includes('secret-token'));
});

test('routeProvider excludes capture-fixture under default fallback policy but allows it on allow-fixture', () => {
  const captureProvider = createCaptureFixtureProvider({
    fixtures: [sanitizedFixtureWithProvenance()],
    decoder: maritimeExampleDecoder(),
    now: () => FIXTURE_NOW,
  });
  const registry = createProviderRegistry([captureProvider]);

  const defaultDecision = routeProvider(registry, { capability: 'vessel_position' });
  assert.equal(defaultDecision.selected, undefined, 'capture-fixture must be excluded under the default allow-terrestrial policy');
  assert.equal(defaultDecision.considered.length, 1);
  assert.equal(defaultDecision.considered[0].providerId, 'capture-fixture');
  assert.equal(defaultDecision.considered[0].skippedReason, 'fallback_policy_excludes_capture');

  const strictDecision = routeProvider(registry, { capability: 'vessel_position', fallbackPolicy: 'strict' });
  assert.equal(strictDecision.selected, undefined);
  assert.equal(strictDecision.considered[0].skippedReason, 'fallback_policy_excludes_capture');

  const openedDecision = routeProvider(registry, { capability: 'vessel_position', fallbackPolicy: 'allow-fixture' });
  assert.equal(openedDecision.selected?.providerId, 'capture-fixture');
});

test('CaptureFixtureProvider is opt-in: explicit registry constructor includes it but default does not', () => {
  const captureProvider = createCaptureFixtureProvider({
    fixtures: [sanitizedFixtureWithProvenance()],
    decoder: maritimeExampleDecoder(),
    now: () => FIXTURE_NOW,
  });
  const optInRegistry = createProviderRegistry([captureProvider]);
  assert.deepEqual(
    optInRegistry.providers().map((p) => p.id),
    ['capture-fixture'],
  );
  // Defaults remain fixture-only — capture-fixture is never auto-loaded.
  assert.deepEqual(createProviderRegistry().providers().map((p) => p.id), ['fixture']);
});

test('capture-fixture imported HAR captures still report FIXTURE_FORMAT_VERSION', () => {
  const fixture = sanitizedFixtureWithProvenance();
  assert.equal(fixture.version, FIXTURE_FORMAT_VERSION);
  assert.equal(fixture.provenance?.liveReplayDisabled, true);
});

test('search without filters returns unsupported_query no-data result', async () => {
  const provider = createCaptureFixtureProvider({
    fixtures: [sanitizedFixtureWithProvenance()],
    decoder: maritimeExampleDecoder(),
    now: () => FIXTURE_NOW,
  });
  const result = await provider.search({});
  assert.ok(isNoDataResult(result));
  assert.equal(result.reason, 'unsupported_query');
});

test('latestPosition without identifier returns unsupported_query', async () => {
  const provider = createCaptureFixtureProvider({
    fixtures: [sanitizedFixtureWithProvenance()],
    decoder: maritimeExampleDecoder(),
    now: () => FIXTURE_NOW,
  });
  const result = await provider.latestPosition({});
  assert.ok(isNoDataResult(result));
  assert.equal(result.reason, 'unsupported_query');
});

test('CaptureFixtureProvider exposes a decoder identity for diagnostics', () => {
  const decoder = maritimeExampleDecoder();
  const provider = new CaptureFixtureProvider({
    fixtures: [sanitizedFixtureWithProvenance()],
    decoder,
    now: () => FIXTURE_NOW,
  });
  assert.equal(provider.decoderId(), 'maritime-example-v1');
});
