import type { Config } from '../config.js';
import { HttpClient, RateLimiter } from '../http.js';
import { isValidLatLon, roundCoord } from '../geo.js';
import {
  arrayOf,
  finiteNumber,
  MAX_NAME_LENGTH,
  nonNegativeInteger,
  objectOf,
  text,
  truncate,
} from '../shape.js';
import type { GeocodeResult } from './nominatim.js';

const OSM_TYPE_NAMES: Record<string, string> = {
  N: 'node',
  W: 'way',
  R: 'relation',
};

/** Photon supports only a handful of languages; anything else falls back to `default`. */
const PHOTON_LANGUAGES = new Set(['en', 'de', 'fr']);

/**
 * Photon (komoot) geocoder — fair-use public instance, typo-tolerant,
 * minutely-updated OSM data. Good for fuzzy place lookup where Nominatim
 * expects well-formed addresses.
 */
export class PhotonBackend {
  private readonly limiter: RateLimiter;

  constructor(
    private readonly http: HttpClient,
    private readonly config: Config,
    limiter?: RateLimiter
  ) {
    this.limiter = limiter ?? new RateLimiter(1100);
  }

  async search(
    query: string,
    options: { limit?: number; language?: string } = {}
  ): Promise<GeocodeResult[]> {
    const params = new URLSearchParams({
      q: query,
      limit: String(options.limit ?? 3),
      lang: PHOTON_LANGUAGES.has(options.language ?? 'en')
        ? (options.language ?? 'en')
        : 'default',
    });
    const data = objectOf(
      await this.http.request(
        'photon',
        `${this.config.photonUrl}/api?${params}`,
        this.limiter
      )
    );
    return arrayOf(data?.features)
      .map((feature) => toResult(feature))
      .filter((result) => result !== null);
  }
}

/** One address part, as Photon wrote it, or nothing. */
function part(value: unknown): string | undefined {
  return text(value, MAX_NAME_LENGTH);
}

/** One GeoJSON feature as a result, or null without a usable coordinate. */
function toResult(feature: unknown): GeocodeResult | null {
  const f = objectOf(feature);
  const coordinates = arrayOf(objectOf(f?.geometry)?.coordinates);
  const lon = finiteNumber(coordinates[0]);
  const lat = finiteNumber(coordinates[1]);
  if (
    !f ||
    lat === undefined ||
    lon === undefined ||
    !isValidLatLon(lat, lon)
  ) {
    return null;
  }
  const p = objectOf(f.properties) ?? {};
  const name = part(p.name) ?? part(p.street);
  const postcode = part(p.postcode);
  const city = part(p.city);
  const label = [
    [name, part(p.housenumber)].filter(Boolean).join(' '),
    postcode && city ? `${postcode} ${city}` : city,
    part(p.state),
    part(p.country),
  ]
    .filter(Boolean)
    .join(', ');
  const result: GeocodeResult = {
    lat: roundCoord(lat),
    lon: roundCoord(lon),
    label: truncate(label, MAX_NAME_LENGTH) || '(unnamed)',
  };
  // Object.hasOwn: osm_type comes from the upstream response — a plain index
  // lookup would resolve prototype keys like "constructor" to a function.
  const osmType =
    typeof p.osm_type === 'string' && Object.hasOwn(OSM_TYPE_NAMES, p.osm_type)
      ? OSM_TYPE_NAMES[p.osm_type]
      : undefined;
  const osmId = nonNegativeInteger(p.osm_id);
  if (osmType && osmId !== undefined) {
    result.osm = `${osmType}/${osmId}`;
  }
  const key = part(p.osm_key);
  const value = part(p.osm_value);
  if (key && value) {
    result.kind = `${key}/${value}`;
  }
  return result;
}
