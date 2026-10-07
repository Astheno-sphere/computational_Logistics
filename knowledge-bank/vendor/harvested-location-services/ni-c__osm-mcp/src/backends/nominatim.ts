import type { Config } from '../config.js';
import { HttpClient, RateLimiter } from '../http.js';
import { isValidLatLon, roundCoord } from '../geo.js';
import {
  arrayOf,
  finiteNumberFromText,
  MAX_NAME_LENGTH,
  nonNegativeInteger,
  objectOf,
  text,
} from '../shape.js';

export interface GeocodeResult {
  lat: number;
  lon: number;
  /** Human-readable place label, e.g. the Nominatim display name. */
  label: string;
  /** OSM element reference like `node/240109189`, when known. */
  osm?: string;
  /** Element class/type, e.g. `tourism/museum`. */
  kind?: string;
}

/** The three element kinds `poi_details` accepts; anything else is not an id. */
const OSM_TYPES = new Set(['node', 'way', 'relation']);

/**
 * Nominatim public API. Usage policy: at most 1 request/second, identifying
 * User-Agent required, results must be cached — the shared HttpClient and the
 * limiter here implement exactly that.
 */
export class NominatimBackend {
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
    options: { limit?: number; language?: string; countrycodes?: string } = {}
  ): Promise<GeocodeResult[]> {
    const params = new URLSearchParams({
      q: query,
      format: 'jsonv2',
      limit: String(options.limit ?? 3),
      'accept-language': options.language ?? 'en',
    });
    if (options.countrycodes) {
      params.set('countrycodes', options.countrycodes.toLowerCase());
    }
    const data = await this.http.request(
      'nominatim',
      `${this.config.nominatimUrl}/search?${params}`,
      this.limiter
    );
    // A hit the shaper refuses is dropped, not fatal: one malformed entry
    // must not take the other results with it.
    return arrayOf(data)
      .map((place) => toResult(place))
      .filter((result) => result !== null);
  }

  async reverse(
    lat: number,
    lon: number,
    language = 'en'
  ): Promise<GeocodeResult | null> {
    const params = new URLSearchParams({
      lat: String(lat),
      lon: String(lon),
      format: 'jsonv2',
      'accept-language': language,
    });
    const data = objectOf(
      await this.http.request(
        'nominatim',
        `${this.config.nominatimUrl}/reverse?${params}`,
        this.limiter
      )
    );
    if (!data || data.error !== undefined) return null;
    return toResult(data);
  }
}

/**
 * One Nominatim place as a result, or null when it has no usable coordinate.
 * Nominatim sends `lat`/`lon` as strings; everything else is taken only in the
 * type the field is documented with, and cut to the result's budget.
 */
function toResult(place: unknown): GeocodeResult | null {
  const p = objectOf(place);
  if (!p) return null;
  const lat = finiteNumberFromText(p.lat);
  const lon = finiteNumberFromText(p.lon);
  if (lat === undefined || lon === undefined || !isValidLatLon(lat, lon)) {
    return null;
  }
  const result: GeocodeResult = {
    lat: roundCoord(lat),
    lon: roundCoord(lon),
    label: text(p.display_name, MAX_NAME_LENGTH) ?? '(unnamed)',
  };
  const osmType = text(p.osm_type, 8);
  const osmId = nonNegativeInteger(p.osm_id);
  if (osmType !== undefined && OSM_TYPES.has(osmType) && osmId !== undefined) {
    result.osm = `${osmType}/${osmId}`;
  }
  const category = text(p.category, 100);
  const type = text(p.type, 100);
  if (category && type) {
    result.kind = `${category}/${type}`;
  }
  return result;
}
