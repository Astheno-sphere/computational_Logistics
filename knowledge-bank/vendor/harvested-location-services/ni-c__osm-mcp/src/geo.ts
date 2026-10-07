export interface LatLon {
  lat: number;
  lon: number;
}

const EARTH_RADIUS_M = 6_371_000;

const toRad = (deg: number): number => (deg * Math.PI) / 180;

/** Great-circle distance in meters (Haversine). */
export function haversineMeters(a: LatLon, b: LatLon): number {
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const sinLat = Math.sin(dLat / 2);
  const sinLon = Math.sin(dLon / 2);
  const h =
    sinLat * sinLat +
    Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * sinLon * sinLon;
  // atan2 rather than asin(sqrt(h)): asin is infinitely sensitive where its
  // argument approaches 1, so at antipodal distances the rounding error of
  // `h` grew to a tenth of a metre out of twenty thousand kilometres — enough
  // to make a detour through a third point come out *shorter* than the direct
  // distance, which the triangle-inequality property caught once in a few
  // thousand runs. atan2 is well-conditioned over the whole range.
  return (
    2 * EARTH_RADIUS_M * Math.atan2(Math.sqrt(h), Math.sqrt(Math.max(0, 1 - h)))
  );
}

/**
 * Parses `"49.7596, 6.6439"` (also without the space) into coordinates.
 * Returns null for anything that is not a plain lat,lon pair.
 */
export function parseCoordinates(input: string): LatLon | null {
  const match =
    /^\s*(-?\d{1,3}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$/.exec(input);
  if (!match) return null;
  const lat = Number(match[1]);
  const lon = Number(match[2]);
  if (!isValidLatLon(lat, lon)) return null;
  return { lat, lon };
}

export function isValidLatLon(lat: number, lon: number): boolean {
  return (
    Number.isFinite(lat) &&
    Number.isFinite(lon) &&
    lat >= -90 &&
    lat <= 90 &&
    lon >= -180 &&
    lon <= 180
  );
}

/** `1234` → `"1.2 km"`, `850` → `"850 m"`. */
export function formatDistance(meters: number): string {
  if (!Number.isFinite(meters)) return 'unknown';
  if (meters < 1000) return `${Math.round(meters)} m`;
  const km = meters / 1000;
  return km < 10 ? `${km.toFixed(1)} km` : `${Math.round(km)} km`;
}

/** `5400` → `"1 h 30 min"`, `90` → `"2 min"`. */
export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds)) return 'unknown';
  const minutes = Math.round(seconds / 60);
  if (minutes < 1) return '< 1 min';
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest > 0 ? `${hours} h ${rest} min` : `${hours} h`;
}

/** Rounds a coordinate to 5 decimals (~1 m) to keep responses compact. */
export function roundCoord(value: number): number {
  return Math.round(value * 1e5) / 1e5;
}

/**
 * Ceiling on the points one isochrone contour may contribute.
 *
 * Every other unbounded thing in this server has an explicit budget — 100 route
 * steps, 60 detail tags, 500 characters per tag value — and the contour geometry
 * had none. Its only bound was the 8 MB response cap, which at roughly twenty
 * bytes per coordinate pair is several hundred thousand points.
 *
 * Set above what that cap can carry at realistic coordinate precision, so a
 * legitimate answer from an engine that barely generalizes still comes back
 * whole. It is a backstop against a degenerate document (`[1,2],` repeated is
 * six bytes a point), not a knob — which is why hitting it is an error with a
 * way forward rather than a silent truncation. Silently keeping the first
 * 50 000 points of a ring would be worse than either: the bounding box computed
 * from them would cover part of the contour and say nothing about it.
 */
export const MAX_CONTOUR_POINTS = 500_000;

/**
 * Flattens a GeoJSON coordinate tree into points.
 *
 * Isochrone engines answer with LineString, Polygon or MultiPolygon geometry
 * depending on version and settings, so the nesting depth is not known in
 * advance. Shared by both isochrone backends: the same walk existed twice, and a
 * bound that has to be added twice is a bound that ends up in one of them.
 */
export function flattenCoordinates(coordinates: unknown): LatLon[] {
  const points: LatLon[] = [];
  const walk = (node: unknown): void => {
    if (!Array.isArray(node)) return;
    // On the globe, not merely numeric: JSON `1e999` parses to Infinity, and
    // one such point would make the bounding box fail the output schema.
    if (
      node.length >= 2 &&
      typeof node[0] === 'number' &&
      typeof node[1] === 'number' &&
      isValidLatLon(node[1], node[0])
    ) {
      if (points.length >= MAX_CONTOUR_POINTS) {
        throw new Error(
          `the isochrone service returned more than ${MAX_CONTOUR_POINTS} contour ` +
            'points, which no usable answer needs — ask for a smaller budget ' +
            '(fewer minutes or kilometers), or point the isochrone engine at an ' +
            'instance that generalizes its contours'
        );
      }
      points.push({ lon: node[0], lat: node[1] });
      return;
    }
    for (const child of node) walk(child);
  };
  walk(coordinates);
  return points;
}

/** Corner coordinates of the smallest box containing every point. */
export interface BoundingBox {
  north: number;
  south: number;
  east: number;
  west: number;
}

/**
 * The bounding box of a set of points.
 *
 * A fold rather than `Math.max(...lats)`, and that is the entire reason this
 * function exists. Argument spread puts every element on the call stack: around
 * 125 000 numbers still work and about 200 000 throw `RangeError: Maximum call
 * stack size exceeded` — a message that tells a model nothing and invites it to
 * retry, and every retry is another rate-limited upstream request. A contour of
 * that size is an ordinary answer from a Valhalla instance that does not
 * generalize.
 */
export function boundingBoxOf(points: readonly LatLon[]): BoundingBox {
  let north = -Infinity;
  let south = Infinity;
  let east = -Infinity;
  let west = Infinity;
  for (const point of points) {
    if (point.lat > north) north = point.lat;
    if (point.lat < south) south = point.lat;
    if (point.lon > east) east = point.lon;
    if (point.lon < west) west = point.lon;
  }
  // `+ 0` folds -0 into 0. A contour on the equator or the meridian can carry
  // both spellings, `>`/`<` keep whichever came first, and -0 serialises as
  // `0` in the text block while `structuredContent` keeps the sign — the two
  // channels of one answer would differ.
  return { north: north + 0, south: south + 0, east: east + 0, west: west + 0 };
}
