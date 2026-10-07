import type { GeoWire } from "@geowirehq/core";
import type { LatLng, TravelMode } from "@geowirehq/schema";
import type { IO } from "../io.js";

export interface RouteArgs {
  waypoints: LatLng[];
  mode?: TravelMode;
  geometry?: boolean;
  json?: boolean;
}

function humanDuration(seconds: number): string {
  const s = Math.round(seconds);
  if (s < 60) return `${s}s`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

function humanDistance(meters: number): string {
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters)} m`;
}

/**
 * 원샷 길찾기 — 경유지들 사이 경로(거리·시간). 무키 OSRM.
 */
export async function runRoute(geo: GeoWire, args: RouteArgs, io: IO): Promise<number> {
  const res = await geo.getRoute({
    waypoints: args.waypoints,
    mode: args.mode ?? "driving",
    geometry: args.geometry ?? false,
  });
  if (args.json) {
    io.out(JSON.stringify(res, null, 2));
    return 0;
  }
  if (res.routes.length === 0) {
    io.out("No route found.");
    return 1;
  }
  const r = res.routes[0]!;
  io.out(`Route: ${humanDistance(r.distanceMeters)}, ${humanDuration(r.durationSeconds)} (${r.provider})`);
  if (r.legs.length > 1) {
    r.legs.forEach((l, i) => {
      io.out(`  leg ${i + 1}: ${humanDistance(l.distanceMeters)}, ${humanDuration(l.durationSeconds)}`);
    });
  }
  if (res.meta.attributions.length) io.out(`Attribution: ${res.meta.attributions.join("; ")}`);
  return 0;
}
