import type { Config } from '../config.js';
import { HttpClient, RateLimiter } from '../http.js';
import { flattenCoordinates, type LatLon } from '../geo.js';
import {
  arrayOf,
  MAX_INSTRUCTION_LENGTH,
  measure,
  numberMatrix,
  objectOf,
  text,
} from '../shape.js';
import type { OsrmMatrix, OsrmRoute, Profile } from './osrm.js';
import type { IsochroneContour } from './valhalla.js';

const ORS_PROFILE: Record<Profile, string> = {
  foot: 'foot-walking',
  car: 'driving-car',
  bike: 'cycling-regular',
};

/**
 * OpenRouteService — active only when ORS_API_KEY is set; replaces OSRM for
 * routes/matrices and Valhalla for isochrones. Free-tier quotas are
 * per-endpoint (directions: 2000/day, 40/min); 403 = daily quota, 429 = minute
 * quota.
 */
export class OrsBackend {
  private readonly limiter: RateLimiter;

  constructor(
    private readonly http: HttpClient,
    private readonly config: Config,
    limiter?: RateLimiter
  ) {
    // Stay comfortably under the 40 requests/minute sliding window.
    this.limiter = limiter ?? new RateLimiter(1600);
  }

  get enabled(): boolean {
    return Boolean(this.config.orsApiKey);
  }

  private async post(
    path: string,
    body: unknown
  ): Promise<Record<string, unknown>> {
    const data = await this.http.request(
      'ors',
      `${this.config.orsUrl}${path}`,
      this.limiter,
      {
        method: 'POST',
        headers: {
          Authorization: this.config.orsApiKey ?? '',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      }
    );
    return objectOf(data) ?? {};
  }

  async route(
    profile: Profile,
    coords: LatLon[],
    includeSteps = false
  ): Promise<OsrmRoute> {
    const data = await this.post(`/v2/directions/${ORS_PROFILE[profile]}`, {
      coordinates: coords.map((c) => [c.lon, c.lat]),
      instructions: includeSteps,
    });
    const route = objectOf(arrayOf(data.routes)[0]);
    if (!route) throw new Error('ORS returned no route');
    const summary = objectOf(route.summary);
    const distance = measure(summary?.distance);
    const duration = measure(summary?.duration);
    if (distance === undefined || duration === undefined) {
      throw new Error(
        'ORS returned a route without a usable distance and duration'
      );
    }
    const segments = arrayOf(route.segments).map((raw) => objectOf(raw) ?? {});
    return {
      distanceMeters: distance,
      durationSeconds: duration,
      legs: segments.map((segment) => ({
        distanceMeters: measure(segment.distance) ?? 0,
        durationSeconds: measure(segment.duration) ?? 0,
      })),
      ...(includeSteps
        ? {
            steps: segments.flatMap((segment) =>
              arrayOf(segment.steps).map((raw) => {
                const step = objectOf(raw) ?? {};
                return {
                  instruction:
                    text(step.instruction, MAX_INSTRUCTION_LENGTH) ?? '',
                  distanceMeters: measure(step.distance) ?? 0,
                };
              })
            ),
          }
        : {}),
    };
  }

  async table(
    profile: Profile,
    origins: LatLon[],
    destinations: LatLon[]
  ): Promise<OsrmMatrix> {
    const locations = [...origins, ...destinations].map((c) => [c.lon, c.lat]);
    const data = await this.post(`/v2/matrix/${ORS_PROFILE[profile]}`, {
      locations,
      sources: origins.map((_, i) => i),
      destinations: destinations.map((_, i) => i + origins.length),
      metrics: ['distance', 'duration'],
    });
    return {
      durations: numberMatrix(data.durations),
      distances: numberMatrix(data.distances),
    };
  }

  async isochrone(
    center: LatLon,
    profile: Profile,
    options: { minutes?: number; kilometers?: number }
  ): Promise<IsochroneContour[]> {
    const isTime = options.minutes !== undefined;
    const data = await this.post(`/v2/isochrones/${ORS_PROFILE[profile]}`, {
      locations: [[center.lon, center.lat]],
      range: [isTime ? options.minutes! * 60 : options.kilometers! * 1000],
      range_type: isTime ? 'time' : 'distance',
    });
    return arrayOf(data.features)
      .map((feature) => objectOf(feature))
      .filter((f) => f !== undefined)
      .map((f) => {
        const value = measure(objectOf(f.properties)?.value) ?? 0;
        return {
          // Normalize back to the Valhalla convention: minutes or kilometers.
          value: isTime ? value / 60 : value / 1000,
          coordinates: flattenCoordinates(objectOf(f.geometry)?.coordinates),
        };
      })
      .filter((c) => c.coordinates.length > 0);
  }
}
