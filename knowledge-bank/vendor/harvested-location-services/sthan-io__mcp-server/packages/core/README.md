# @sthan/core

TypeScript client for [sthan.io](https://sthan.io) APIs.

## Usage

```typescript
import { SthanClient } from "@sthan/core";

const client = new SthanClient({ apiKey: "sthan_test_your_key" });

const result = await client.verifyAddress("123 Main St, New York, NY 10001");
console.log(result.Result);
```

## Methods

| Method | Description |
|--------|-------------|
| `verifyAddress(address)` | Verify US address deliverability |
| `parseAddress(address)` | Parse freeform address into components |
| `autocompleteAddress(text)` | Address suggestions from partial input |
| `autocompleteCity(text, displayType?)` | City suggestions |
| `autocompleteZipCode(text, displayType?)` | ZIP code suggestions |
| `geocodeAddress(address)` | Forward geocode (address to coordinates) |
| `reverseGeocode(lat, lon)` | Reverse geocode (coordinates to address) |
| `ipGeolocation(ip)` | IP address location lookup |

## License

MIT
