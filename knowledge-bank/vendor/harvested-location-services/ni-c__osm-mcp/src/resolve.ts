import { parseCoordinates, roundCoord, type LatLon } from './geo.js';
import type { GeocodeResult, NominatimBackend } from './backends/nominatim.js';
import type { PhotonBackend } from './backends/photon.js';

export interface Place extends LatLon {
  label: string;
}

export type GeocodeProvider = 'nominatim' | 'photon';

export class PlaceResolver {
  constructor(
    private readonly nominatim: NominatimBackend,
    private readonly photon: PhotonBackend
  ) {}

  search(
    query: string,
    options: {
      provider?: GeocodeProvider;
      limit?: number;
      language?: string;
      countrycodes?: string;
    } = {}
  ): Promise<GeocodeResult[]> {
    if (options.provider === 'photon') {
      return this.photon.search(query, options);
    }
    return this.nominatim.search(query, options);
  }

  /**
   * Turns a tool input into coordinates: either a literal `"lat,lon"` pair or
   * a place name that is geocoded (top hit). Geocode responses are cached by
   * the HTTP layer, so repeated waypoints do not hit Nominatim again.
   */
  async resolve(input: string, language = 'en'): Promise<Place> {
    const coords = parseCoordinates(input);
    if (coords) {
      return {
        lat: roundCoord(coords.lat),
        lon: roundCoord(coords.lon),
        label: `${roundCoord(coords.lat)},${roundCoord(coords.lon)}`,
      };
    }
    const results = await this.nominatim.search(input, { limit: 1, language });
    const hit = results[0];
    if (!hit) {
      throw new Error(
        `no location found for "${input}" — try the geocode tool to disambiguate, ` +
          'or pass coordinates as "lat,lon"'
      );
    }
    return { lat: hit.lat, lon: hit.lon, label: hit.label };
  }

  resolveAll(inputs: string[], language = 'en'): Promise<Place[]> {
    // Sequential on purpose: the Nominatim limiter serializes anyway, and this
    // keeps the order stable.
    return inputs.reduce<Promise<Place[]>>(
      async (acc, input) => [
        ...(await acc),
        await this.resolve(input, language),
      ],
      Promise.resolve([])
    );
  }
}
