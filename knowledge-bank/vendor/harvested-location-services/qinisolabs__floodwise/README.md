<div align="center">

<img src="https://qinisolabs.github.io/floodwise/logo.svg" width="96" height="96" alt="Qiniso" />

# floodwise

**England flood-risk by postcode for AI agents — verified Environment Agency data, not guesses.**

*Verified, trustworthy data tools for AI agents. "Qiniso" means "truth" in Zulu.*

[Website](https://qinisolabs.github.io/floodwise/) · [npm](https://www.npmjs.com/package/floodwise) · [MCP Registry](https://registry.modelcontextprotocol.io/v0/servers?search=floodwise)

</div>

---

Ask an LLM "what's the flood risk at SW1A 1AA?" and it will answer confidently — but it **cannot know**: per-postcode flood risk is specific, curated data that lives in a government dataset, not in a model's weights. **floodwise** looks the postcode up in the Environment Agency's official *"Flood risk: postcode search tool"* data and returns the real long-term risk band — or an honest *"not found"* instead of a guess.

## ⚠️ Read this first — what floodwise is and isn't

- **England only.** The data is the Environment Agency's, which covers **England**. Wales (Natural Resources Wales), Scotland (SEPA) and Northern Ireland (DfI) are **not** covered. A valid Welsh/Scottish postcode returns *"not found"*, never a guess.
- **Area-level, not property-level.** The risk is for *the area around* the addresses in a postcode — not a specific building. The EA states this data is *"generally not suitable for property level assessment"*.
- **Long-term risk, not a live warning.** It reflects the long-term annual chance of flooding, not whether flooding is happening now or forecast. It is **not** insurance, underwriting, surveying or professional advice.

## Add it to Claude

floodwise runs locally over stdio (no key, no login). Once it's on npm, add it under `mcpServers` in your client config:

```json
{ "command": "npx", "args": ["-y", "floodwise"] }
```

## Use it as a library

```bash
npm i floodwise
```

```ts
import { floodRiskByPostcode, validatePostcode } from "floodwise";

floodRiskByPostcode("SW1A 1AA");
// {
//   postcode: "SW1A 1AA", found: true, headlineRisk: "Very Low",
//   addressesAtRisk: { high: 0, medium: 0, low: 0 }, groundwater: "Unlikely",
//   coverage: "England", dataset: "ea-official", ...
// }

floodRiskByPostcode("EH1 1AA").found;   // false — valid postcode, but Scotland (out of EA coverage), no guess
validatePostcode("ec1a1bb");            // { valid: true, postcode: "EC1A 1BB", outcode: "EC1A", incode: "1BB" }
```

Postcodes are accepted spaced or unspaced, any case. A well-formed postcode that isn't in the loaded England dataset returns `found: false` with a clear note — it never invents a risk level.

## Tools — 2

| Tool | What it answers |
| --- | --- |
| **flood_risk_by_postcode** | The EA long-term flood-risk band (High/Medium/Low/Very Low) for an England postcode, address counts per band, and the groundwater indication |
| **validate_postcode** | Is this a well-formed UK postcode? (deterministic format check + outcode/incode split) |

## Data

The flood data is the Environment Agency **"Flood risk: postcode search tool data"** (England), published as open data under the **Open Government Licence v3.0**. Each postcode carries the number of addresses whose surrounding area is at high (≥3.3%/yr), medium (1–3.3%) or low (0.1–1%) long-term risk from rivers, sea or surface water (the highest of these), plus a separate groundwater *Possible/Unlikely* indication. Refreshed roughly quarterly.

> This repository ships an **illustrative starter sample** (non-geographic `ZZ` pseudo-postcodes) so tests run out of the box — every response from it is tagged `dataset: "sample"`. To load the real data, download `Postcodes_Risk_Assessment_All.csv` from [data.gov.uk](https://www.data.gov.uk/) / the Defra Data Services Platform and run:
>
> ```bash
> npm run build-data /path/to/Postcodes_Risk_Assessment_All.csv 2025-Q4
> npm run build && npm test
> ```

Attribution: *Contains public sector information licensed under the Open Government Licence v3.0. © Environment Agency copyright and/or database right.* See `NOTICE`.

## What it is *not*

- **Not advice.** Not insurance, underwriting, surveying, mortgage or legal advice; not a property-level survey.
- **Not all flood types.** Excludes flooding from highway drains, sewers and overland flow; groundwater is reported separately and isn't combined into the headline band.
- **Not the whole UK.** England only (see above).
- **Not a guesser.** Unknown/out-of-coverage postcodes return an honest "not found", never a fabricated risk level.

## Architecture

A single TypeScript package exposing one MCP server over **stdio** (local / `npx`), driven by the same `core.ts` tool definitions that power the importable library. A Cloudflare Worker entry is included for a future hosted edge endpoint — note the full England dataset (~1.6M postcodes) exceeds the Worker bundle limit, so the hosted build will move the data into Cloudflare D1 (a follow-on); the npm library and stdio server run the full dataset directly.

```bash
npm install
npm run build
npm test
```

## Privacy

This tool runs locally on your machine and is built not to collect, store, or transmit your data — no analytics, no telemetry, no account. All reference data is bundled — no network calls, and nothing leaves your device. Full policy: <https://qinisolabs.github.io/privacy.html>.

## License

Apache-2.0. Flood data © Environment Agency, Open Government Licence v3.0; see `NOTICE`.
