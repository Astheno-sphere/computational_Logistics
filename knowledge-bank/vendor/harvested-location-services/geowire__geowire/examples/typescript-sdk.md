# GeoWire as an embedded TypeScript library

No server, no HTTP. Import `@geowirehq/core` and run the whole gateway in-process
— fallback, merge, dedup, budgets, and policy all included.

```bash
npm i @geowirehq/core @geowirehq/provider-nominatim
# optional providers:
npm i @geowirehq/provider-google @geowirehq/provider-internal
```

## Minimal (zero keys)

```ts
import { createGeoWire } from "@geowirehq/core";
import { createNominatimProvider } from "@geowirehq/provider-nominatim";

const geo = createGeoWire({ providers: [createNominatimProvider()] });

const { results, meta } = await geo.searchPlaces({
  query: "Starbucks",
  near: { latitude: 37.7749, longitude: -122.4194 },
  radiusMeters: 3000,
});

for (const p of results) {
  console.log(p.name, p.location, "via", p.sources.map((s) => s.provider).join("+"));
}
console.log("providers used:", meta.providersUsed);
```

## Multi-provider with merge, dedup, and a budget

```ts
import { createGeoWire } from "@geowirehq/core";
import { createNominatimProvider } from "@geowirehq/provider-nominatim";
import { createGoogleProvider } from "@geowirehq/provider-google";

const geo = createGeoWire({
  providers: [
    createGoogleProvider({ apiKey: process.env.GOOGLE_MAPS_API_KEY }), // BYOK; skipped if unset
    createNominatimProvider(),
  ],
  config: {
    routing: { defaultStrategy: "merge" },
    budget: { perRequestMaxUSD: 0.05 },
    dedup: { mergeThreshold: 0.75 },
  },
});

const { results, meta } = await geo.searchPlaces({
  query: "Blue Bottle",
  near: { latitude: 37.7749, longitude: -122.4194 },
  radiusMeters: 2000,
});

console.log("dedup:", meta.dedup);          // { before, after }
console.log("cost:", meta.estimatedCostUSD);
```

## The full surface

```ts
await geo.searchPlaces({ query, near?, radiusMeters?, country?, limit?, options? });
await geo.geocode({ address, country?, limit? });
await geo.reverseGeocode({ location: { latitude, longitude } });
await geo.getPlace({ id: "google:ChIJ..." });   // getPlace-capable providers only
geo.listProviders();                             // ids, capabilities, auth, attribution
```

All inputs are validated with Zod; every response includes the `meta` provenance
block (see [docs/recipes.md §4](../docs/recipes.md#4-read-a-response-provenance--transparency)).

## Your own places as a provider

```ts
import { createInternalProvider } from "@geowirehq/provider-internal";

const geo = createGeoWire({
  providers: [
    createInternalProvider({ source: "./my-places.csv" }), // your stores/POIs (CSV path)
    createNominatimProvider(),
  ],
  config: { routing: { defaultStrategy: "merge" } },
});
```

Writing a brand-new provider is ~30 minutes — see
[CONTRIBUTING.md](../CONTRIBUTING.md#write-a-provider-in-30-minutes).
