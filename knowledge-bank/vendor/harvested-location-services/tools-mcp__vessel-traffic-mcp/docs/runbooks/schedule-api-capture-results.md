# Schedule API capture results

Purpose: record sanitized browser-captured API shapes for carrier schedule
lookup. Raw response bodies, screenshots, and private run artifacts stay under
`captures/private/` and must not be committed.

## Attribution / source URL rule

Any MCP result promoted from these captures must expose the original service
and a user-facing URL. For Tradelinx this means:

- `source.provider`: `tradlinx-schedule`
- `source.landingUrl`: `https://www.tradlinx.com/ko/schedule?tab=fcl` or
  `https://www.tradlinx.com/ko/schedule?tab=lcl`
- Result-level source URL: the visible result page, for example
  `https://www.tradlinx.com/ko/ocean-schedule-fcl?org=105169&des=105234&day=2026-05-18`
- When present, keep upstream carrier schedule links such as `linePlanUrl` as
  secondary source links, not as a replacement for Tradelinx attribution.
- Client display text may present the source as the returned URL instead of a
  vendor display label, but the structured metadata must keep enough provenance
  for audit/debugging.

## Tradelinx Schedule

Capture date: 2026-05-18.

Capture method: normal Playwright-controlled browser session against public,
no-login pages. No Cloudflare or CAPTCHA block was observed. The page makes
unauthenticated session checks (`/session`, `/auth/sso/token`) that report login
required or 401, but the schedule endpoints below returned data without login.

Probe route:

- Origin: Busan, `KRPUS`, Tradelinx location id `105169`
- Destination: Rotterdam, `NLRTM`, Tradelinx location id `105234`
- UI source pages:
  - `https://www.tradlinx.com/ko/schedule?tab=fcl`
  - `https://www.tradlinx.com/ko/schedule?tab=lcl`

Observed UI behavior:

- Port selection opens an in-page major-port list. No XHR/fetch autocomplete API
  was observed for the `부산` / `로테르담` text entry itself.
- FCL result routing uses UN/LOCODEs in the API and internal location ids in the
  browser URL.
- LCL result routing uses internal location ids in the API and browser URL.

### FCL schedule search

```text
GET https://api.tradlinx.com/fclschedule?<cacheBust>&depPort=<originUnlocode>&arrPort=<destinationUnlocode>
```

Observed route:

```text
GET https://api.tradlinx.com/fclschedule?<cacheBust>&depPort=KRPUS&arrPort=NLRTM
```

Observed response envelope:

```json
{
  "result": true,
  "errorCode": null,
  "errorMsg": null,
  "data": []
}
```

Observed data fields:

- Schedule/carrier: `schId`, `shprCd`, `shprNm`, `srvc`, `linePlanUrl`
- Vessel/voyage: `vslNm`, `voyage`
- Route: `depPortCd`, `depPortNm`, `arrPortCd`, `arrPortNm`
- Times: `depEta`, `depEtd`, `arrEta`, `arrEtd`, `cargoCloseDtm`, `docCloseDtm`
- Commercial/display: `tt`, `transTp`, `twentyFare`, `fortyFare`

Observed count for KRPUS to NLRTM: 215 schedules. `transTp` values observed:
`1` for direct and `2` for transshipment.

### FCL detail

Clicking a row-level `Detail` button called:

```text
GET https://api.tradlinx.com/fclschedule/<schId>?<cacheBust>
```

Observed data fields:

- Segment: `schSubId`, `schId`, `seq`, `shprCd`, `shprNm`, `srvcCd`
- Segment ports/times: `depLocationId`, `depPortNm`, `depTmnlNm`, `depEtd`,
  `depEta`, `arrLocationId`, `arrPortNm`, `arrTmnlNm`, `arrEta`, `arrEtd`
- Vessel: `vessel.vslId`, `vessel.vslNm`, `vessel.imoNo`, `vessel.mmsi`,
  `vessel.callSign`, `vessel.cntryCd`, `vessel.cntryNm`, `vessel.teu`
- Voyage: `vslNm`, `voyage`

The same detail expansion also called vessel schedule endpoints for each
segment vessel:

```text
GET https://api.tradlinx.com/vesselSchedule/<shprCd>/<vslId>?<cacheBust>
```

Observed vessel schedule fields:

- Carrier/vessel: `shprCd`, `shprNm`, `vslNm`, `vslId`
- Port: `port.locationId`, `port.portCd`, `port.portNm`, `port.cntryCd`,
  `port.label`
- Voyage/timing: `inVoyage`, `outVoyage`, `tmnlNm`, `arrDtm`, `berthnDtm`,
  `depDtm`

The detail expansion also called:

```text
GET https://api.tradlinx.com/soperContactLst/<shprCd>?<cacheBust>
```

This returns carrier contact rows. Do not promote raw contact values into public
fixtures or user-facing MCP responses until contact-data handling has been
reviewed.

### LCL schedule search

```text
GET https://api.tradlinx.com/lclschedule?<cacheBust>&depPort=<originLocationId>&arrPort=<destinationLocationId>
```

Observed route:

```text
GET https://api.tradlinx.com/lclschedule?<cacheBust>&depPort=105169&arrPort=105234
```

Observed data fields:

- Schedule/forwarder: `schId`, `fwdrCd`, `fwdrNm`
- Vessel/voyage: `vslNm`, `voyage`, `vslTypeCd`
- Timing: `docCloseDtm`, `cargoCloseDtm`, `depEtd`, `arrEta`
- Route: `depLocationId`, `depPortNm`, `depCntryNm`, `arrLocationId`,
  `arrPortNm`, `arrCntryNm`
- Contact/CFS: `chargeNm`, `tel`, `cfs`, `cfsAdrs`, `cfsCode`, `cfsPerson`,
  `cfsTel`, `cfsFax`
- Other: `remark`

Observed count for Busan location `105169` to Rotterdam location `105234`: 15
schedules. Treat `chargeNm`, `cfs`, and related contact/CFS fields as sensitive
business contact text until promotion policy is reviewed.

### Non-schedule endpoints

The browser also called banner/ad/content endpoints such as:

- `GET https://api.tradlinx.com/banner/KR/NL/CNTRY_FCL_SCHEDULE?...`
- `GET https://api.tradlinx.com/banner/KR/NL/CNTRY_LCL_SCHEDULE?...`
- `GET https://api.tradlinx.com/lingo/rolling-banners/v2?...`
- `GET/POST/PUT https://app.tradlinx.com/adcr/...`

These are not schedule-data sources and should not feed MCP schedule results.

## Adapter status

`src/providers/tradlinx.ts` implements the FCL/LCL route schedule endpoints for
explicit opt-in runtime use through:

```text
VESSEL_MCP_ENABLE_PUBLIC_PROVIDERS=tradlinx
```

The adapter exposes `carrier_schedule_search` only. The captured FCL detail,
vesselSchedule, and carrier-contact endpoints remain reference material until a
stable `vslId` resolution path and contact-data policy are reviewed.

## Guardrails

- Do not commit raw responses, screenshots, HAR files, cookies, or private
  browser artifacts.
- Do not replay login, SSO, account, billing, or ad-click endpoints.
- Default tests must not call live Tradelinx endpoints.
- The adapter must use conservative pacing and must expose a user-facing source
  URL in every returned schedule result.
