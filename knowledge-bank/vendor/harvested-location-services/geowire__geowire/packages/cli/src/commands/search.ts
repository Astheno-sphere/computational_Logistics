import type { GeoWire } from "@geowirehq/core";
import type { LatLng, Strategy } from "@geowirehq/schema";
import type { IO } from "../io.js";
import { formatSearchTable } from "../format.js";

export interface SearchArgs {
  query: string;
  near?: LatLng;
  radiusMeters?: number;
  limit?: number;
  country?: string;
  strategy?: Strategy;
  json?: boolean;
}

/**
 * 원샷 터미널 검색 (설계 §9 데모 킬러 기능).
 * geo를 주입받아 검색하고 결과를 표(또는 --json)로 출력한다.
 */
export async function runSearch(geo: GeoWire, args: SearchArgs, io: IO): Promise<number> {
  const res = await geo.searchPlaces({
    query: args.query,
    near: args.near,
    radiusMeters: args.radiusMeters,
    country: args.country,
    limit: args.limit,
    options: args.strategy ? { strategy: args.strategy } : undefined,
  });

  if (args.json) {
    io.out(JSON.stringify(res, null, 2));
  } else {
    io.out(formatSearchTable(res.results, res.meta));
  }
  return 0;
}
