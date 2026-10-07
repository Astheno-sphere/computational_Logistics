#!/usr/bin/env node
// Live smoke test against the real public OSM services — run on demand with
// `npm run smoke`, and never in the pull-request gate: it exercises
// third-party infrastructure that nobody here pays for, and its results depend
// on live map data, so a pull request could go red because somebody edited a
// building. CI runs it on the weekly schedule only, where a failure is a
// report that something moved rather than a block on anybody's work.
// Requires a prior `npm run build`.
//
// The foot-vs-car check at the end is the guard against the classic OSRM demo
// pitfall: with the wrong URL layout the server silently returns car routes
// for every profile, and walking times come out impossibly fast.
import { StdioClientTransport } from '@modelcontextprotocol/client/stdio';
import { Client } from '@modelcontextprotocol/client';

const serverPath = new URL('../dist/index.js', import.meta.url).pathname;
const client = new Client({ name: 'smoke', version: '0.0.0' });
await client.connect(
  new StdioClientTransport({ command: process.execPath, args: [serverPath] })
);

let failures = 0;

async function call(name, args, check) {
  try {
    const result = await client.callTool({ name, arguments: args });
    const text = result.content?.[0]?.text ?? '';
    if (result.isError) throw new Error(text.slice(0, 300));
    const value = check ? check(text) : undefined;
    console.log(`ok   ${name} ${value !== undefined ? `(${value})` : ''}`);
    return text;
  } catch (error) {
    failures += 1;
    console.error(`FAIL ${name}: ${error.message}`);
    return '';
  }
}

function json(text) {
  return JSON.parse(text.slice(text.indexOf('{')));
}

console.log('osm-mcp live smoke test — talking to the real public services\n');

let portaNigraOsm = 'way/24526783';
await call('geocode', { query: 'Porta Nigra, Trier' }, (t) => {
  const first = json(t).results[0];
  if (!first) throw new Error('no geocode result');
  if (first.osm) portaNigraOsm = first.osm;
  return first.label;
});
await call(
  'geocode',
  { query: 'porta ngira trier', provider: 'photon' },
  (t) => json(t).results[0]?.label ?? '(no photon hit)'
);
await call('reverse_geocode', { latitude: 49.7546, longitude: 6.6424 }, (t) =>
  json(t).result?.label?.slice(0, 60)
);

const foot = await call(
  'route',
  { waypoints: ['Trier', 'Luxembourg'], profile: 'foot' },
  (t) => `${json(t).distance}, ${json(t).duration}`
);
const car = await call(
  'route',
  { waypoints: ['Trier', 'Luxembourg'], profile: 'car' },
  (t) => `${json(t).distance}, ${json(t).duration}`
);

await call(
  'route_matrix',
  {
    origins: ['Porta Nigra, Trier', 'Trier Hauptbahnhof'],
    destinations: ['Kaiserthermen, Trier'],
    profile: 'foot',
  },
  (t) => `durations ${JSON.stringify(json(t).durations_minutes)}`
);
await call(
  'optimize_route',
  {
    stops: [
      'Porta Nigra, Trier',
      'Kaiserthermen, Trier',
      'Trier Hauptbahnhof',
      'Amphitheater, Trier',
    ],
    profile: 'foot',
  },
  (t) => json(t).optimized_order.join(' → ')
);
await call(
  'isochrone',
  { center: 'Porta Nigra, Trier', profile: 'foot', minutes: 15 },
  (t) => `reach north ${json(t).reach.north}`
);
await call(
  'find_nearby_pois',
  { near: 'Porta Nigra, Trier', category: 'cafe', limit: 3 },
  (t) =>
    json(t)
      .results.map((r) => r.name)
      .join(', ')
);
await call('poi_details', { osm_id: portaNigraOsm }, (t) => json(t).name);
await call(
  'suggest_meeting_point',
  { locations: ['Porta Nigra, Trier', 'Trier Hauptbahnhof'], profile: 'foot' },
  (t) => json(t).suggestion?.name ?? json(t).note
);
await call(
  'straight_line_distance',
  { from: 'Trier', to: 'Luxembourg' },
  (t) => json(t).distance
);
await call(
  'map_link',
  { from: 'Trier', to: 'Luxembourg', profile: 'car' },
  (t) => json(t).directions.slice(0, 60)
);

// Profile guard: walking must take much longer than driving.
if (foot && car) {
  const footSeconds = json(foot).duration_s;
  const carSeconds = json(car).duration_s;
  if (footSeconds > carSeconds * 3) {
    console.log(
      `ok   profile guard (foot ${footSeconds}s vs car ${carSeconds}s — profiles are real)`
    );
  } else {
    failures += 1;
    console.error(
      `FAIL profile guard: foot ${footSeconds}s vs car ${carSeconds}s — ` +
        'walking should be far slower; the OSRM profile prefix may be broken'
    );
  }
}

await client.close();
console.log(
  failures === 0 ? '\nAll smoke checks passed.' : `\n${failures} FAILURES`
);
process.exit(failures === 0 ? 0 : 1);
