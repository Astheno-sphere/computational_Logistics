#!/usr/bin/env node

import { createReadStream } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';

import { createFixtureProvider } from '../../dist/providers/fixture.js';
import { createMyShipTrackingProvider } from '../../dist/providers/myshiptracking.js';

const rootDir = fileURLToPath(new URL('.', import.meta.url));
const publicDir = join(rootDir, 'public');
const preferredPort = Number.parseInt(process.env.VESSEL_MAP_UI_PORT ?? '8787', 10);
const maxPortAttempts = 10;
const liveProvider = createMyShipTrackingProvider();
const fixtureProvider = createFixtureProvider();
const mapUiMode = process.env.VESSEL_MAP_UI_MODE ?? 'auto';
const fallbackEnabled = mapUiMode !== 'live';

const contentTypes = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
};

function json(res, status, body) {
  const payload = JSON.stringify(body, null, 2);
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
  });
  res.end(payload);
}

function inferMovement(position) {
  const speed = Number.isFinite(position.speedKnots) ? position.speedKnots : undefined;
  if (speed === undefined) return { label: '상태 미확인', tone: 'unknown' };
  if (speed <= 0.2) return { label: '정지 또는 접안 추정', tone: 'idle' };
  if (speed <= 2) return { label: '저속 이동', tone: 'slow' };
  return { label: '항해 중', tone: 'moving' };
}

function queryFromRaw(raw) {
  const value = raw.trim();
  if (/^[0-9]{9}$/.test(value)) return { mmsi: value, limit: 5 };
  if (/^[0-9]{7}$/.test(value)) return { imo: value, limit: 5 };
  return { name: value, limit: 5 };
}

async function lookupWithProvider(provider, rawQuery, mode) {
  const query = rawQuery.trim();
  if (!query) {
    return {
      status: 400,
      body: {
        ok: false,
        reason: 'empty_query',
        message: '선박명, IMO, MMSI 중 하나를 입력하세요.',
      },
    };
  }

  const searchResult = await provider.search(queryFromRaw(query));
  if (!searchResult.ok) {
    return {
      status: searchResult.reason === 'rate_limited' ? 429 : 502,
      body: {
        ok: false,
        reason: searchResult.reason,
        message: searchResult.message,
        source: searchResult.source,
        caveats: searchResult.caveats,
      },
    };
  }

  const primary = searchResult.data.matches.find((candidate) => candidate.mmsi) ?? searchResult.data.matches[0];
  if (!primary?.mmsi) {
    return {
      status: 404,
      body: {
        ok: false,
        reason: 'mmsi_not_found',
        message: '검색 결과에서 위치 조회용 MMSI를 찾지 못했습니다.',
        candidates: searchResult.data.matches,
        source: searchResult.source,
      },
    };
  }

  const positionResult = await provider.latestPosition({ mmsi: primary.mmsi });
  if (!positionResult.ok) {
    return {
      status: positionResult.reason === 'rate_limited' ? 429 : 502,
      body: {
        ok: false,
        reason: positionResult.reason,
        message: positionResult.message,
        identity: primary,
        candidates: searchResult.data.matches,
        source: positionResult.source,
        caveats: positionResult.caveats,
      },
    };
  }

  return {
    status: 200,
    body: {
      ok: true,
      mode,
      query,
      identity: {
        ...primary,
        ...positionResult.data.identity,
      },
      candidates: searchResult.data.matches,
      position: positionResult.data,
      movement: inferMovement(positionResult.data),
      source: positionResult.source,
      sourceUrl: positionResult.source.landingUrl ?? 'https://github.com/tools-mcp/vessel-traffic-mcp',
      retrievedAt: positionResult.retrievedAt,
      caveats: positionResult.caveats,
    },
  };
}

async function lookupVessel(rawQuery) {
  if (mapUiMode === 'fixture') {
    return lookupWithProvider(fixtureProvider, rawQuery, 'fixture');
  }

  const liveResult = await lookupWithProvider(liveProvider, rawQuery, 'live');
  if (liveResult.body.ok || !fallbackEnabled) {
    return liveResult;
  }

  const fixtureResult = await lookupWithProvider(fixtureProvider, rawQuery, 'fixture');
  if (!fixtureResult.body.ok) {
    return liveResult;
  }

  return {
    status: 200,
    body: {
      ...fixtureResult.body,
      fallback: {
        fromProvider: 'myshiptracking',
        reason: liveResult.body.reason,
        message: liveResult.body.message,
        sourceUrl: liveResult.body.source?.landingUrl,
      },
      caveats: [
        'Live MyShipTracking lookup was unavailable; showing deterministic fixture data.',
        ...(fixtureResult.body.caveats ?? []),
      ],
    },
  };
}

async function serveStatic(req, res, pathname) {
  const relative = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  const normalized = normalize(relative);
  if (normalized.startsWith('..')) {
    json(res, 403, { ok: false, reason: 'forbidden' });
    return;
  }

  const filePath = join(publicDir, normalized);
  try {
    await readFile(filePath);
  } catch {
    json(res, 404, { ok: false, reason: 'not_found' });
    return;
  }

  const type = contentTypes[extname(filePath)] ?? 'application/octet-stream';
  res.writeHead(200, {
    'content-type': type,
    'cache-control': 'no-store',
  });
  createReadStream(filePath).pipe(res);
}

function createAppServer() {
  return createServer(async (req, res) => {
    try {
      const url = new URL(req.url ?? '/', 'http://127.0.0.1');
      if (url.pathname === '/api/vessel') {
        if (req.method !== 'GET') {
          json(res, 405, { ok: false, reason: 'method_not_allowed' });
          return;
        }
        const result = await lookupVessel(url.searchParams.get('query') ?? '');
        json(res, result.status, result.body);
        return;
      }

      if (url.pathname === '/api/provider') {
        if (req.method !== 'GET') {
          json(res, 405, { ok: false, reason: 'method_not_allowed' });
          return;
        }
        const [liveStatus, liveSources, fixtureStatus, fixtureSources] = await Promise.all([
          liveProvider.status(),
          liveProvider.dataSources(),
          fixtureProvider.status(),
          fixtureProvider.dataSources(),
        ]);
        json(res, 200, {
          ok: true,
          mode: mapUiMode,
          fallbackEnabled,
          status: liveStatus,
          sources: liveSources,
          fixture: {
            status: fixtureStatus,
            sources: fixtureSources,
          },
        });
        return;
      }

      await serveStatic(req, res, url.pathname);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      json(res, 500, { ok: false, reason: 'server_error', message });
    }
  });
}

async function listenWithPortFallback(port) {
  for (let attempt = 0; attempt < maxPortAttempts; attempt += 1) {
    const candidate = port + attempt;
    const server = createAppServer();
    try {
      await new Promise((resolve, reject) => {
        server.once('error', reject);
        server.listen(candidate, '127.0.0.1', () => {
          server.off('error', reject);
          resolve();
        });
      });
      return { server, port: candidate };
    } catch (error) {
      server.close();
      if (!error || error.code !== 'EADDRINUSE') throw error;
    }
  }
  throw new Error(`No free local port found from ${port} to ${port + maxPortAttempts - 1}.`);
}

const handle = await listenWithPortFallback(preferredPort);
globalThis.vesselMapUiServer = handle.server;
const { port } = handle;
console.log(`vessel-map-ui listening on http://127.0.0.1:${port}`);
setInterval(() => {}, 2 ** 30);
