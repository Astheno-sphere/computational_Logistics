import type { Config } from '../config.js';
import { HttpClient, RateLimiter } from '../http.js';
import { flattenCoordinates, type LatLon } from '../geo.js';
import { arrayOf, measure, objectOf } from '../shape.js';
import type { Profile } from './osrm.js';

const COSTING: Record<Profile, string> = {
  foot: 'pedestrian',
  car: 'auto',
  bike: 'bicycle',
};

export interface IsochroneContour {
  /** The contour value: minutes for time, kilometers for distance. */
  value: number;
  /** All contour ring coordinates, for bounding-box summaries. */
  coordinates: LatLon[];
}

/** FOSSGIS Valhalla instance — used for isochrones, which OSRM cannot do. */
export class ValhallaBackend {
  private readonly limiter: RateLimiter;

  constructor(
    private readonly http: HttpClient,
    private readonly config: Config,
    limiter?: RateLimiter
  ) {
    this.limiter = limiter ?? new RateLimiter(1100);
  }

  async isochrone(
    center: LatLon,
    profile: Profile,
    options: { minutes?: number; kilometers?: number }
  ): Promise<IsochroneContour[]> {
    const contour =
      options.minutes !== undefined
        ? { time: options.minutes }
        : { distance: options.kilometers };
    const request = {
      locations: [{ lat: center.lat, lon: center.lon }],
      costing: COSTING[profile],
      contours: [contour],
      polygons: false,
    };
    const params = new URLSearchParams({ json: JSON.stringify(request) });
    const data = objectOf(
      await this.http.request(
        'valhalla',
        `${this.config.valhallaUrl}/isochrone?${params}`,
        this.limiter
      )
    );
    return arrayOf(data?.features)
      .map((feature) => objectOf(feature))
      .filter((f) => f !== undefined)
      .map((f) => ({
        value: measure(objectOf(f.properties)?.contour) ?? 0,
        coordinates: flattenCoordinates(objectOf(f.geometry)?.coordinates),
      }))
      .filter((c) => c.coordinates.length > 0);
  }
}
