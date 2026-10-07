import type { GeoWire } from "@geowirehq/core";
import type { IO } from "../io.js";
import { formatPlace } from "../format.js";

export interface GetArgs {
  id: string;
  json?: boolean;
}

/**
 * 단일 장소 상세 조회 — `provider:providerPlaceId` 참조(예: `nominatim:node/240109189`).
 * 내부 `gwp_` ID는 역추적 불가라 null → 종료 코드 1.
 */
export async function runGet(geo: GeoWire, args: GetArgs, io: IO): Promise<number> {
  const place = await geo.getPlace({ id: args.id });
  if (!place) {
    io.err(
      `No place found for id: ${args.id}\n` +
        `getPlace needs a provider that supports it (currently Google, with GOOGLE_MAPS_API_KEY).\n` +
        `Use a provider reference from a result's sources, e.g. 'google:ChIJN1t_tDeuEmsRUsoyG83frY4'.`,
    );
    return 1;
  }
  if (args.json) {
    io.out(JSON.stringify(place, null, 2));
  } else {
    io.out(formatPlace(place));
  }
  return 0;
}
