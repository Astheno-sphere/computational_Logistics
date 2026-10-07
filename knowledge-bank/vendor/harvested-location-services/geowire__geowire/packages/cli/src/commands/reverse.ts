import type { GeoWire } from "@geowirehq/core";
import type { LatLng } from "@geowirehq/schema";
import type { IO } from "../io.js";
import { formatSearchTable } from "../format.js";

export interface ReverseArgs {
  location: LatLng;
  json?: boolean;
}

/**
 * 원샷 리버스 지오코딩 — 좌표 → 가장 가까운 주소/장소.
 * 응답 형태가 search와 같아 동일한 표 포매터를 재사용한다.
 */
export async function runReverse(geo: GeoWire, args: ReverseArgs, io: IO): Promise<number> {
  const res = await geo.reverseGeocode({ location: args.location });
  if (args.json) {
    io.out(JSON.stringify(res, null, 2));
  } else {
    io.out(formatSearchTable(res.results, res.meta));
  }
  return 0;
}
