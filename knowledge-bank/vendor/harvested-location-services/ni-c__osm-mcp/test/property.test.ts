import fc from 'fast-check';
import { describe, expect, it } from 'vitest';

import {
  boundingBoxOf,
  formatDistance,
  formatDuration,
  haversineMeters,
  isValidLatLon,
  parseCoordinates,
  roundCoord,
  type LatLon,
} from '../src/geo.js';

/**
 * Properties of the geometry helpers.
 *
 * Everything here is arithmetic, which is the one kind of code where an example
 * test is least useful and a property most: a distance function is either right
 * for every pair of points or wrong in a way three chosen pairs will not show.
 * `parseCoordinates` additionally reads a string a caller typed, and its
 * refusals are what keep a malformed pair from becoming a plausible-looking
 * location somewhere else in the world.
 */

const RUNS = { numRuns: 500 };

const latitude = fc.double({ min: -90, max: 90, noNaN: true });
const longitude = fc.double({ min: -180, max: 180, noNaN: true });
const point: fc.Arbitrary<LatLon> = fc.record({
  lat: latitude,
  lon: longitude,
});

/**
 * How far a detour may come out short of the direct distance before it
 * counts as a broken triangle inequality: the haversine's own rounding, in
 * two parts that dominate at opposite ends of the range.
 *
 * Relative, because near the antipode the formula is ill-conditioned and not
 * by fractions of a millimetre: `a` goes to 1, so `atan2(√a, √(1-a))` divides
 * by a square root of something the size of the machine epsilon, and the
 * error in a single distance reaches R·√ε ≈ 9.5 cm. Measured, from the run
 * that caught the old bound: the three points (0,0), (6.04e-7,0),
 * (0,179.99999879) leave the detour 6.7 cm — 3.4e-9 relative — short of
 * direct, so the previous 1e-9 was a factor of three too tight. 1e-7 clears
 * three such evaluations with room to spare.
 *
 * Absolute, because across the antimeridian the error does not shrink with
 * the distance. A longitude near ±180° is only representable to
 * ulp(180°) ≈ 3 nm, and `b.lon - a.lon` there is close to ±360°, so `sin`
 * works on an argument close to ±π and loses R·ulp(π) ≈ 6 nm per distance
 * however short the distance is. Measured: three points on the equator at
 * lon 179.99999911907594, 179.99999999906078 and -179.99999999835805, all
 * within 10 cm of each other, leave the detour 9.9 nm — 1.01e-7 relative —
 * short of direct, which the relative bound alone rejected. A micrometre
 * clears that with room to spare.
 *
 * Both stay far below the thousands of kilometres a sign error or a swapped
 * lat/lon costs.
 */
const slack = (direct: number): number => direct * 1e-7 + 1e-6;

describe('distance behaves like a distance', () => {
  it('is zero from a point to itself', () => {
    fc.assert(
      fc.property(point, (a) => {
        expect(haversineMeters(a, a)).toBeCloseTo(0, 6);
      }),
      RUNS
    );
  });

  it('is symmetric', () => {
    fc.assert(
      fc.property(point, point, (a, b) => {
        expect(haversineMeters(a, b)).toBeCloseTo(haversineMeters(b, a), 6);
      }),
      RUNS
    );
  });

  /**
   * The triangle inequality is the property that catches a sign error or a
   * swapped latitude and longitude — both of which still produce a plausible
   * number for any single pair.
   */
  it('never takes a detour that is shorter than going direct', () => {
    fc.assert(
      fc.property(point, point, point, (a, b, c) => {
        const direct = haversineMeters(a, c);
        const detour = haversineMeters(a, b) + haversineMeters(b, c);
        expect(detour).toBeGreaterThanOrEqual(direct - slack(direct));
      }),
      RUNS
    );
  });

  // The two triples that each broke an earlier bound, pinned so the tolerance
  // cannot be narrowed again without a failing test saying why.
  it.each([
    {
      name: 'nearly antipodal',
      a: { lat: 0, lon: 0 },
      b: { lat: 6.04e-7, lon: 0 },
      c: { lat: 0, lon: 179.99999879 },
    },
    {
      name: 'a few centimetres across the antimeridian',
      a: { lat: 0, lon: 179.99999911907594 },
      b: { lat: 0, lon: 179.99999999906078 },
      c: { lat: 0, lon: -179.99999999835805 },
    },
  ])('keeps the triangle inequality for the $name triple', ({ a, b, c }) => {
    const direct = haversineMeters(a, c);
    const detour = haversineMeters(a, b) + haversineMeters(b, c);
    expect(detour).toBeGreaterThanOrEqual(direct - slack(direct));
  });

  it('measures across the antimeridian the short way round', () => {
    // The wrap itself, not only its rounding: 179.9999° and -179.9999° are
    // about 22 m apart, not 40 000 km.
    const east = { lat: 0, lon: 179.9999 };
    const west = { lat: 0, lon: -179.9999 };
    expect(haversineMeters(east, west)).toBeCloseTo(22.24, 1);
    expect(haversineMeters(west, east)).toBeCloseTo(22.24, 1);
  });

  /** Half the circumference is the furthest two points on a sphere can be. */
  it('never exceeds half the circumference', () => {
    fc.assert(
      fc.property(point, point, (a, b) => {
        expect(haversineMeters(a, b)).toBeLessThanOrEqual(20_015_200);
      }),
      RUNS
    );
  });
});

describe('coordinates parse back to what was written', () => {
  it('a formatted pair round trips', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: -9000, max: 9000 }),
        fc.integer({ min: -18000, max: 18000 }),
        fc.constantFrom(', ', ',', ' , ', '  ,  '),
        (latHundredths, lonHundredths, separator) => {
          const lat = latHundredths / 100;
          const lon = lonHundredths / 100;
          const parsed = parseCoordinates(`${lat}${separator}${lon}`);
          expect(parsed).toEqual({ lat, lon });
        }
      ),
      RUNS
    );
  });

  /**
   * A pair outside the valid range is refused rather than clamped.
   *
   * Clamping would turn a typo into a location — a longitude of 200 becoming
   * 180 puts the answer in the Pacific and says nothing about it.
   */
  it('refuses a pair outside the valid range', () => {
    fc.assert(
      fc.property(
        fc.oneof(
          fc.integer({ min: 91, max: 999 }),
          fc.integer({ min: -999, max: -91 })
        ),
        (lat) => {
          expect(parseCoordinates(`${lat}, 0`)).toBeNull();
          expect(isValidLatLon(lat, 0)).toBe(false);
        }
      ),
      RUNS
    );
  });

  it('refuses anything that is not a plain pair', () => {
    fc.assert(
      fc.property(fc.string({ unit: 'binary' }), (input) => {
        const parsed = parseCoordinates(input);
        if (parsed === null) return;
        expect(isValidLatLon(parsed.lat, parsed.lon)).toBe(true);
      }),
      RUNS
    );
  });

  it('rounds to five decimals and no further', () => {
    fc.assert(
      fc.property(fc.double({ min: -180, max: 180, noNaN: true }), (value) => {
        const rounded = roundCoord(value);
        expect(Math.abs(rounded - value)).toBeLessThanOrEqual(5e-6 + 1e-9);
        expect(Math.round(rounded * 1e5)).toBeCloseTo(rounded * 1e5, 6);
      }),
      RUNS
    );
  });
});

describe('a bounding box covers everything it was given', () => {
  /**
   * The one thing a bounding box must never do is leave a point out — the
   * comment on `MAX_CONTOUR_POINTS` says exactly why silently keeping the first
   * 50 000 points of a ring would be worse than refusing: the box computed from
   * them would cover part of the contour and say nothing about it.
   */
  it('contains every point', () => {
    fc.assert(
      fc.property(
        fc.array(point, { minLength: 1, maxLength: 40 }),
        (points) => {
          const box = boundingBoxOf(points);
          for (const p of points) {
            expect(p.lat).toBeGreaterThanOrEqual(box.south);
            expect(p.lat).toBeLessThanOrEqual(box.north);
            expect(p.lon).toBeGreaterThanOrEqual(box.west);
            expect(p.lon).toBeLessThanOrEqual(box.east);
          }
        }
      ),
      RUNS
    );
  });

  it('is never inverted', () => {
    fc.assert(
      fc.property(
        fc.array(point, { minLength: 1, maxLength: 40 }),
        (points) => {
          const box = boundingBoxOf(points);
          expect(box.north).toBeGreaterThanOrEqual(box.south);
          expect(box.east).toBeGreaterThanOrEqual(box.west);
        }
      ),
      RUNS
    );
  });

  it('does not depend on the order the points arrived in', () => {
    fc.assert(
      fc.property(
        fc.array(point, { minLength: 1, maxLength: 20 }),
        (points) => {
          expect(boundingBoxOf(points)).toEqual(
            boundingBoxOf(points.toReversed())
          );
        }
      ),
      RUNS
    );
  });
});

describe('formatting never invents a number', () => {
  it('a distance is always a number with a unit, or unknown', () => {
    fc.assert(
      fc.property(
        fc.oneof(
          fc.double({ min: 0, max: 1e8, noNaN: true }),
          fc.constantFrom(Number.NaN, Number.POSITIVE_INFINITY)
        ),
        (meters) => {
          expect(formatDistance(meters)).toMatch(/^(unknown|[\d.]+ (m|km))$/);
        }
      ),
      RUNS
    );
  });

  it('a duration is always readable, or unknown', () => {
    fc.assert(
      fc.property(
        fc.oneof(
          fc.double({ min: 0, max: 1e7, noNaN: true }),
          fc.constantFrom(Number.NaN, Number.POSITIVE_INFINITY)
        ),
        (seconds) => {
          expect(formatDuration(seconds)).toMatch(
            /^(unknown|< 1 min|\d+ min|\d+ h( \d+ min)?)$/
          );
        }
      ),
      RUNS
    );
  });

  /**
   * A duration below a minute says so rather than rounding to `0 min`, which
   * would read as "no time at all" for a leg that is genuinely a short walk.
   */
  it('never reports zero minutes', () => {
    fc.assert(
      fc.property(fc.double({ min: 0, max: 59, noNaN: true }), (seconds) => {
        expect(formatDuration(seconds)).not.toBe('0 min');
      }),
      RUNS
    );
  });
});
