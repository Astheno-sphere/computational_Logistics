import { describe, expect, it } from 'vitest';

import {
  boundingBoxOf,
  flattenCoordinates,
  formatDistance,
  formatDuration,
  haversineMeters,
  MAX_CONTOUR_POINTS,
  parseCoordinates,
  roundCoord,
} from '../src/geo.js';

describe('haversineMeters', () => {
  it('measures Trier to Luxembourg at roughly 40 km', () => {
    const meters = haversineMeters(
      { lat: 49.7596, lon: 6.6439 },
      { lat: 49.6116, lon: 6.1319 }
    );
    expect(meters).toBeGreaterThan(38_000);
    expect(meters).toBeLessThan(43_000);
  });

  it('returns 0 for identical points', () => {
    expect(haversineMeters({ lat: 50, lon: 6 }, { lat: 50, lon: 6 })).toBe(0);
  });
});

describe('parseCoordinates', () => {
  it('parses "lat,lon" with and without spaces', () => {
    expect(parseCoordinates('49.7596, 6.6439')).toEqual({
      lat: 49.7596,
      lon: 6.6439,
    });
    expect(parseCoordinates('-33.9,151.2')).toEqual({ lat: -33.9, lon: 151.2 });
  });

  it('rejects place names and out-of-range values', () => {
    expect(parseCoordinates('Trier')).toBeNull();
    expect(parseCoordinates('Trier, Germany')).toBeNull();
    expect(parseCoordinates('91,0')).toBeNull();
    expect(parseCoordinates('0,181')).toBeNull();
  });
});

describe('formatting', () => {
  it('formats distances', () => {
    expect(formatDistance(850)).toBe('850 m');
    expect(formatDistance(1234)).toBe('1.2 km');
    expect(formatDistance(41_500)).toBe('42 km');
  });

  it('formats durations', () => {
    expect(formatDuration(20)).toBe('< 1 min');
    expect(formatDuration(90)).toBe('2 min');
    expect(formatDuration(5400)).toBe('1 h 30 min');
    expect(formatDuration(7200)).toBe('2 h');
  });

  it('rounds coordinates to ~1 m precision', () => {
    expect(roundCoord(49.75961234)).toBe(49.75961);
  });
});

describe('isochrone contour geometry', () => {
  it('finds the bounding box of a contour too large to spread', () => {
    /*
     * `Math.max(...lats)` puts every element on the call stack. On this runtime
     * 125 000 arguments still work and 150 000 already throw `RangeError:
     * Maximum call stack size exceeded` — and a Valhalla instance that does not
     * generalize answers a 120-minute car isochrone with several hundred
     * thousand points, which the 8 MB response cap happily admits.
     *
     * The failure was not just a crash: it reached the model as "Maximum call
     * stack size exceeded", which says nothing it can act on, so it retries —
     * and every retry is another rate-limited upstream request.
     */
    const points = Array.from({ length: 200_000 }, (_, index) => ({
      lat: 49 + (index % 1000) / 1000,
      lon: 6 + (index % 997) / 1000,
    }));
    points.push({ lat: 51.5, lon: 2.25 });

    const box = boundingBoxOf(points);
    expect(box.north).toBe(51.5);
    expect(box.west).toBe(2.25);
    expect(box.south).toBe(49);
    expect(box.east).toBeCloseTo(6.996, 5);
  });

  it('flattens LineString, Polygon and MultiPolygon geometry alike', () => {
    // The nesting depth is not knowable in advance: it depends on the engine,
    // its version and whether polygons were asked for.
    expect(flattenCoordinates([6, 49])).toEqual([{ lon: 6, lat: 49 }]);
    expect(flattenCoordinates([[[[6, 49]]]])).toEqual([{ lon: 6, lat: 49 }]);
    expect(flattenCoordinates('not geometry')).toEqual([]);
  });

  it('refuses a contour past the point ceiling instead of truncating it', () => {
    // A cap that silently kept the first N points of a ring would compute a
    // bounding box over part of the contour and report it as the whole thing —
    // a wrong answer, which is worse than the error it replaced. So it stops,
    // and says what to do.
    const many = Array.from({ length: MAX_CONTOUR_POINTS + 1 }, () => [6, 49]);
    expect(() => flattenCoordinates(many)).toThrow(/smaller budget/);
  });
});
