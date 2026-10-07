import type { Config } from '../config.js';
import { HttpClient, OsmApiError, RateLimiter, Semaphore } from '../http.js';
import { isValidLatLon, roundCoord, type LatLon } from '../geo.js';
import {
  arrayOf,
  finiteNumber,
  nonNegativeInteger,
  objectOf,
  stringTags,
} from '../shape.js';

export interface OverpassElement {
  type: 'node' | 'way' | 'relation';
  id: number;
  /** Present when the element (or its centre) has a valid coordinate. */
  lat?: number;
  lon?: number;
  /** Always a string-to-string map, bounded, possibly empty. */
  tags: Record<string, string>;
}

export interface Poi extends LatLon {
  osm: string;
  name: string;
  tags: Record<string, string>;
}

const ELEMENT_TYPES = new Set(['node', 'way', 'relation']);

/**
 * Overpass API. The public main instance grants ~2 concurrent slots per IP and
 * asks clients to back off on 429 — this backend caps concurrency, and on
 * 429/5xx fails over to the next configured mirror instead of hammering the
 * same server.
 */
export class OverpassBackend {
  private readonly semaphore = new Semaphore(2);
  private readonly limiter: RateLimiter;
  private readonly retryDelay: (ms: number) => Promise<void>;

  constructor(
    private readonly http: HttpClient,
    private readonly config: Config,
    limiter?: RateLimiter,
    retryDelay?: (ms: number) => Promise<void>
  ) {
    this.limiter = limiter ?? new RateLimiter(1100);
    this.retryDelay =
      retryDelay ?? ((ms) => new Promise((resolve) => setTimeout(resolve, ms)));
  }

  /**
   * Runs a query and answers with the shaped elements. Elements the shaper
   * refuses (no type, no integer id) are dropped one by one, never the answer.
   */
  async query(ql: string): Promise<OverpassElement[]> {
    const release = await this.semaphore.acquire();
    try {
      let lastError: unknown;
      let attempt = 0;
      for (const endpoint of this.config.overpassUrls) {
        // Never walk the mirror list back-to-back — a failing burst across
        // all public interpreters is exactly the pattern they ban clients for.
        if (attempt > 0) await this.retryDelay(1000 * attempt);
        attempt += 1;
        try {
          const data = objectOf(
            await this.http.request('overpass', endpoint, this.limiter, {
              method: 'POST',
              headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
              body: `data=${encodeURIComponent(ql)}`,
              timeoutMs: 40_000,
            })
          );
          return arrayOf(data?.elements)
            .map((element) => toElement(element))
            .filter((element) => element !== null);
        } catch (error) {
          lastError = error;
          const status = error instanceof OsmApiError ? error.status : 0;
          // 429/504 = out of slots, 5xx = instance trouble: try the mirror.
          // So is an interpreter that never answers — a timeout carries no
          // status, and without this a hanging endpoint ended the walk before
          // the next one was asked. Anything else (bad query, network
          // refusal) will not improve there.
          if (status === 429 || status >= 500 || isTimeout(error)) continue;
          throw error;
        }
      }
      throw lastError instanceof Error
        ? new Error(
            `all Overpass endpoints failed (last: ${lastError.message}). ` +
              'The public servers may be overloaded — wait ~30 seconds and retry.'
          )
        : lastError;
    } finally {
      release();
    }
  }

  async findNearby(
    center: LatLon,
    selector: TagSelector,
    radiusMeters: number,
    limit: number
  ): Promise<Poi[]> {
    const ql =
      `[out:json][timeout:25];` +
      `nwr${selectorToQl(selector)}(around:${Math.round(radiusMeters)},${center.lat},${center.lon});` +
      `out center tags ${limit};`;
    return (await this.query(ql))
      .map((el) => toPoi(el))
      .filter((poi) => poi !== null);
  }

  async byId(
    type: 'node' | 'way' | 'relation',
    id: number
  ): Promise<OverpassElement | null> {
    const ql = `[out:json][timeout:25];${type}(${id});out center tags;`;
    const elements = await this.query(ql);
    return elements[0] ?? null;
  }
}

export interface TagSelector {
  key: string;
  value?: string;
}

const TAG_PART = /^[A-Za-z0-9_:-]+$/;

/**
 * Validates a `key` or `key=value` tag filter. The strict charset is what makes
 * interpolating it into Overpass QL safe — anything else is rejected before it
 * reaches the query.
 */
export function parseTagSelector(input: string): TagSelector {
  const [key, value, ...rest] = input.split('=');
  if (
    rest.length > 0 ||
    !key ||
    !TAG_PART.test(key) ||
    (value !== undefined && !TAG_PART.test(value))
  ) {
    throw new Error(
      `invalid tag filter "${input}" — use "key" or "key=value" with letters, ` +
        'digits, underscore, colon and hyphen only (e.g. "amenity=restaurant")'
    );
  }
  return value === undefined ? { key } : { key, value };
}

function selectorToQl(selector: TagSelector): string {
  return selector.value === undefined
    ? `["${selector.key}"]`
    : `["${selector.key}"="${selector.value}"]`;
}

/**
 * One raw Overpass element as the shape the tools read, or null when it has
 * no type or no integer id. Coordinates are taken from the element or its
 * `center`, and only when they are finite and on the globe; tags are always a
 * bounded string map — a mirror that sends `null` for a value, or an object,
 * sends no tag.
 */
export function toElement(raw: unknown): OverpassElement | null {
  const element = objectOf(raw);
  if (!element) return null;
  const type = element.type;
  if (typeof type !== 'string' || !ELEMENT_TYPES.has(type)) return null;
  const id = nonNegativeInteger(element.id);
  if (id === undefined) return null;
  const center = objectOf(element.center);
  const lat = finiteNumber(element.lat) ?? finiteNumber(center?.lat);
  const lon = finiteNumber(element.lon) ?? finiteNumber(center?.lon);
  return {
    type: type as OverpassElement['type'],
    id,
    ...(lat !== undefined && lon !== undefined && isValidLatLon(lat, lon)
      ? { lat: roundCoord(lat), lon: roundCoord(lon) }
      : {}),
    tags: stringTags(element.tags),
  };
}

function toPoi(element: OverpassElement): Poi | null {
  if (element.lat === undefined || element.lon === undefined) return null;
  return {
    osm: `${element.type}/${element.id}`,
    lat: element.lat,
    lon: element.lon,
    name: element.tags.name ?? '(unnamed)',
    tags: element.tags,
  };
}

/** `AbortSignal.timeout` rejects with a `TimeoutError`, while fetching or while reading the body. */
function isTimeout(error: unknown): boolean {
  return error instanceof Error && error.name === 'TimeoutError';
}
