# GeoWire recipes

Practical, copy-pasteable recipes for the things GeoWire is good at. Every
example works against a real running GeoWire — the outputs below are real, not
mocked (except where a recipe needs a Google key, which is clearly labeled).

Each recipe shows the relevant surfaces: **CLI**, **REST**, **SDK**, and/or an
**MCP** prompt. Pick whichever fits.

- [1. Search & geocode with zero API keys](#1-search--geocode-with-zero-api-keys)
- [2. Search near a point (bias + hard radius)](#2-search-near-a-point-bias--hard-radius)
- [3. Reverse geocode](#3-reverse-geocode)
- [4. Read a response: provenance & transparency](#4-read-a-response-provenance--transparency)
- [5. Merge Google + OpenStreetMap and de-duplicate](#5-merge-google--openstreetmap-and-de-duplicate)
- [6. Cost budgets: cap what you spend](#6-cost-budgets-cap-what-you-spend)
- [7. Route by country](#7-route-by-country)
- [8. Add your own places (CSV) as a provider](#8-add-your-own-places-csv-as-a-provider)
- [9. Self-host with Docker + REST](#9-self-host-with-docker--rest)

> **Data honesty:** the default provider is OpenStreetMap/Nominatim, a
> **geocoder** — excellent for place names, addresses, and landmarks, but weak
> on category words ("coffee", "pharmacy"), business hours, and "open now",
> and uneven outside Europe. Add a Google Maps key (recipe 5) for full business
> data. GeoWire tells you exactly which source every field came from, so you're
> never guessing.

---

## 1. Search & geocode with zero API keys

No signup, no key. OpenStreetMap is the default.

**CLI**
```bash
npx @geowirehq/cli search "Eiffel Tower"
npx @geowirehq/cli search "Gyeongbokgung Palace" --limit 1
```

```
Found 2 places · first-success · nominatim · 1208ms

#  Name          Distance  Address                                   Sources
─  ────────────  ────────  ────────────────────────────────────────  ─────────
1  Tour Eiffel   -         Tour Eiffel, 5, Avenue Anatole France, …  nominatim
2  Eiffel Tower  -         Eiffel Tower, Improvement District No. …  nominatim
Attribution: © OpenStreetMap contributors
```

**MCP** (Claude Desktop / Cursor / Claude Code) — just ask:
> "Where is the Colosseum? Give me its coordinates."

The agent calls `geocode_address` and gets back `41.89094, 12.49190`.

**SDK**
```ts
import { createGeoWire } from "@geowirehq/core";
import { createNominatimProvider } from "@geowirehq/provider-nominatim";

const geo = createGeoWire({ providers: [createNominatimProvider()] });
const { results } = await geo.geocode({ address: "Eiffel Tower" });
console.log(results[0].location); // { latitude: 48.858..., longitude: 2.294... }
```

---

## 2. Search near a point (bias + hard radius)

Pass `near` to bias results to a location. Add `radiusMeters` to **hard-limit**
results to that radius — anything outside is dropped.

**CLI**
```bash
npx @geowirehq/cli search "Starbucks" --near 37.7749,-122.4194 --radius 3000
```

```
Found 3 places · first-success · nominatim · 742ms

#  Name       Distance  Address                                       Sources
─  ─────────  ────────  ────────────────────────────────────────────  ─────────
1  Starbucks  410m      201 Powell St, San Francisco, CA 94102, US    nominatim
2  Starbucks  980m      333 Market St, San Francisco, CA 94105, US    nominatim
3  Starbucks  1620m     1231 Market St, San Francisco, CA 94103, US   nominatim
Attribution: © OpenStreetMap contributors
```

**REST**
```bash
curl -X POST http://localhost:4980/v1/places/search \
  -H "content-type: application/json" \
  -d '{"query":"Starbucks","near":{"latitude":37.7749,"longitude":-122.4194},"radiusMeters":3000}'
```

> Tip: `near` without `radiusMeters` biases (soft); with `radiusMeters` it
> hard-restricts. Use a *name* ("Starbucks") rather than a category ("coffee")
> on OpenStreetMap — see the data-honesty note above.

---

## 3. Reverse geocode

Coordinates → the nearest addressable place.

**CLI**
```bash
npx @geowirehq/cli reverse 37.8199,-122.4783
```

**REST**
```bash
curl "http://localhost:4980/v1/reverse-geocode?lat=37.8199&lon=-122.4783"
```

**MCP** — "What's at 37.8199, -122.4783?"

---

## 4. Read a response: provenance & transparency

Every response is fully attributed — which providers were **used / skipped /
failed**, per-field sourcing, confidence, cache status, and (for paid
providers) estimated cost. No black box.

```bash
npx @geowirehq/cli search "Golden Gate Bridge" --limit 1 --json
```

```jsonc
{
  "results": [
    {
      "id": "gwp_CvWvRZrFtegkJPxP9CW0",
      "name": "Golden Gate Bridge",
      "categories": ["bridge"],
      "location": { "latitude": 37.8199286, "longitude": -122.4782551 },
      "address": {
        "formatted": "Golden Gate Bridge, San Francisco, California, United States",
        "country": "US", "region": "California", "city": "San Francisco"
      },
      "confidence": 0.495,
      "sources": [
        {
          "provider": "nominatim",
          "providerPlaceId": "way/27385590",
          "fetchedAt": "2026-07-18T14:08:29.415Z",
          "confidence": 0.495,
          "fields": ["name", "location", "categories", "address"]  // which fields this source contributed
        }
      ],
      "attributions": ["© OpenStreetMap contributors"]
    }
  ],
  "meta": {
    "providersUsed":   [{ "provider": "nominatim", "resultCount": 1, "latencyMs": 2449 }],
    "providersSkipped": [],   // e.g. { provider: "google", reason: "MISSING_CREDENTIALS" }
    "providersFailed":  [],   // e.g. { provider: "google", reason: "TIMEOUT" }
    "strategy": "first-success",
    "cache": { "hit": false },
    "attributions": ["© OpenStreetMap contributors"]
    // when merging: "dedup": { "before": 6, "after": 4 }
    // when paid:    "estimatedCostUSD": 0.032
  }
}
```

`sources[].fields` is the key differentiator: after a merge you can see that the
phone number came from Google while the coordinates came from OSM.

---

## 5. Merge Google + OpenStreetMap and de-duplicate

Call **both** providers in parallel, merge the same real-world place into one
result, and keep both sources attributed. This is where GeoWire earns its keep.

**Config** (`geowire.config.yaml`)
```yaml
providers:
  google:    { enabled: true, priority: 50 }   # needs GOOGLE_MAPS_API_KEY
  nominatim: { enabled: true, priority: 10 }
routing:
  defaultStrategy: merge          # call all eligible providers, then dedup
dedup:
  mergeThreshold: 0.75            # 0-1; higher = stricter
```

**Run**
```bash
GOOGLE_MAPS_API_KEY=... npx @geowirehq/cli search "Blue Bottle" \
  --near 37.7749,-122.4194 --radius 2000 --strategy merge --json
```

The same café returned by Google and OSM collapses into **one** result whose
`sources` lists both, and `meta.dedup` reports the collapse:

```jsonc
{
  "results": [{
    "name": "Blue Bottle Coffee",
    "location": { "latitude": 37.7764, "longitude": -122.4230 },
    "business": { "openingHours": "Mon-Sun 07:00-19:00", "rating": 4.4 }, // from Google
    "sources": [
      { "provider": "google",    "providerPlaceId": "ChIJ...", "fields": ["name","business","contact"] },
      { "provider": "nominatim", "providerPlaceId": "node/...", "fields": ["location","address"] }
    ]
  }],
  "meta": { "strategy": "merge", "dedup": { "before": 3, "after": 1 }, "estimatedCostUSD": 0.032 }
}
```

> This example needs a Google key, so the response above is illustrative of the
> shape. Dedup uses location (Haversine) + name (Jaro-Winkler, corporate-suffix
> aware) + address + phone + website similarity, clustered with union-find.

---

## 6. Cost budgets: cap what you spend

Set a per-request or monthly USD ceiling. Paid providers over budget are
**skipped** (not failed) with `QUOTA_EXCEEDED`; free providers (OSM, your CSV)
always run, so you never get an empty result just because you're frugal.

**Config**
```yaml
budget:
  perRequestMaxUSD: 0.01     # a single Google search is $0.032 → skipped
  monthlyUSD: 50
```

With this, a `merge` request drops Google (too expensive for this call) and
still answers from OpenStreetMap. The response tells you plainly:

```jsonc
"meta": {
  "providersUsed":    [{ "provider": "nominatim", "resultCount": 4 }],
  "providersSkipped": [{ "provider": "google", "reason": "QUOTA_EXCEEDED" }],
  "strategy": "merge"
}
```

**Or route by cost.** The `cost-aware` strategy tries providers cheapest-first
(free before paid) and stops at the first with results — so you only pay for
Google when OpenStreetMap/Kakao/your CSV can't answer:

```bash
GOOGLE_MAPS_API_KEY=... npx @geowirehq/cli search "Eiffel Tower" --strategy cost-aware
# used: nominatim · cost: $0   (Google never called — OSM answered)
```

`weighted` goes further: it orders providers per request by a score over
priority, cost, and **coverage** — so a `country: US` request favors providers
that cover the US (Yelp, Google), a cost-sensitive one routes to free providers
first, and a `country: KR` request routes to Kakao/Naver. Tune the mix in
`routing.providerWeights`.

---

## 7. Route by country

Prefer different providers per country — e.g. your own data + Yelp in the US,
Kakao in Korea, OSM everywhere else.

**Config**
```yaml
routing:
  defaultStrategy: first-success
  countries:
    US: { providers: ["internal", "yelp", "google", "nominatim"], strategy: merge }
    KR: { providers: ["kakao", "nominatim"] }
```

Pass `country` on the request (`--country US`, or `"country":"US"`), and the
plan uses that country's provider order and strategy.

---

## 8. Add your own places (CSV) as a provider

Turn a CSV of your stores/POIs into a first-class provider that participates in
search, fallback, and merge — no code.

**`my-places.csv`** (see [`examples/customer-csv/`](../examples/customer-csv/))
```csv
id,name,latitude,longitude,category,address,phone
store-001,Acme Coffee Downtown SF,37.7749,-122.4194,cafe,"123 Market St, San Francisco, CA",+1-415-555-0142
```

**Run**
```bash
GEOWIRE_INTERNAL_CSV=./my-places.csv npx @geowirehq/cli search "Acme" --near 37.7749,-122.4194
```

Your places come back tagged `sources: internal`, and with `strategy: merge`
they de-duplicate against Google/OSM the same as any other provider — so your
canonical store data can override or enrich public data.

---

## 9. Self-host with Docker + REST

```bash
docker run -p 4980:4980 \
  -e GOOGLE_MAPS_API_KEY=... \
  geowire/geowire:latest
```

Then hit the REST API (interactive docs at **http://localhost:4980/docs**):

| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/places/search` | Search |
| GET  | `/v1/geocode?address=...` | Address → coordinates |
| GET  | `/v1/reverse-geocode?lat=..&lon=..` | Coordinates → address |
| GET  | `/v1/places/{provider:id}` | One place by reference |
| GET  | `/v1/providers` | List providers + status |
| GET  | `/v1/health` | Health check |

Protect it with `GEOWIRE_API_KEYS=key1,key2` (comma-separated Bearer tokens).

---

Need a provider that isn't here (Mapbox, Foursquare, Kakao, Naver)? Adding one
is ~30 minutes — see [CONTRIBUTING.md](../CONTRIBUTING.md#write-a-provider-in-30-minutes).
