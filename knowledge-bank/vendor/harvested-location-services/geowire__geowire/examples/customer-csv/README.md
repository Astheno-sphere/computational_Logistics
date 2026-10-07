# Your own places as a provider

Put your stores/locations in a CSV and GeoWire searches them alongside (or ranked
above) public data.

## CSV format

Header row required. Recognized columns (aliases in parentheses):

- `store_id` (`id`, `code`) — stable id
- `name` (`store_name`, `title`) — **required**
- `latitude` (`lat`) / `longitude` (`lon`, `lng`) — **required**
- `address` (`addr`)
- `phone` (`tel`)
- `website` (`url`)
- `opening_hours` (`hours`)
- `category` (`categories`) — comma/semicolon separated

Extra columns are ignored. Rows without a name or valid coordinates are skipped.

## Run it

```bash
# CLI / server
GEOWIRE_INTERNAL_CSV=./my-places.csv npx @geowirehq/cli search "Acme Coffee"

# or via config (recommended — set priority so your data ranks first)
npx @geowirehq/cli --config ./geowire.config.yaml
```

```yaml
# geowire.config.yaml
providers:
  nominatim: { enabled: true }
  internal: { enabled: true, source: ./my-places.csv, priority: 100 }
routing:
  defaultStrategy: merge
```

With `merge`, a store that also exists in OpenStreetMap is deduplicated into a
single result carrying both sources — your data wins field-by-field where it has
higher priority.

## SDK

```ts
import { createGeoWire } from "@geowirehq/core";
import { createNominatimProvider } from "@geowirehq/provider-nominatim";
import { createInternalProvider } from "@geowirehq/provider-internal";

const geo = createGeoWire({
  providers: [
    createInternalProvider({ source: "./my-places.csv" }),
    createNominatimProvider(),
  ],
  config: { providers: { internal: { priority: 100 } }, routing: { defaultStrategy: "merge" } },
});
```
