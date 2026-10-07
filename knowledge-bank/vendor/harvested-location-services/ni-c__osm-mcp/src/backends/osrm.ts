import type { Config } from '../config.js';
import { HttpClient, RateLimiter, upstreamText } from '../http.js';
import type { LatLon } from '../geo.js';
import {
  arrayOf,
  measure,
  MAX_NAME_LENGTH,
  nonNegativeInteger,
  numberMatrix,
  objectOf,
  text,
} from '../shape.js';

export type Profile = 'foot' | 'car' | 'bike';

/**
 * On the FOSSGIS instance (routing.openstreetmap.de) the profile is selected
 * exclusively by this path prefix. The profile segment inside the OSRM path
 * (`/route/v1/driving/…`) is NOT evaluated by the demo servers — putting
 * `walking` there silently returns car routes, a bug most OSM wrappers share.
 */
const PROFILE_PREFIX: Record<Profile, string> = {
  car: 'routed-car',
  bike: 'routed-bike',
  foot: 'routed-foot',
};

export interface OsrmLeg {
  distanceMeters: number;
  durationSeconds: number;
  summary?: string;
}

export interface OsrmStep {
  instruction: string;
  distanceMeters: number;
}

export interface OsrmRoute {
  distanceMeters: number;
  durationSeconds: number;
  legs: OsrmLeg[];
  steps?: OsrmStep[];
}

export interface OsrmMatrix {
  /** durations[i][j] in seconds, null where no route exists. */
  durations: (number | null)[][];
  /** distances[i][j] in meters, null where no route exists. */
  distances: (number | null)[][];
}

export interface OsrmTrip {
  /** Visiting order as indices into the input coordinate list. */
  order: number[];
  distanceMeters: number;
  durationSeconds: number;
  legs: OsrmLeg[];
}

/** A route or trip after shaping: the two numbers every answer needs, and the legs as sent. */
interface ShapedRoute {
  distanceMeters: number;
  durationSeconds: number;
  rawLegs: unknown[];
}

/** OSRM demo instance operated by FOSSGIS — max 1 request/second, fair use. */
export class OsrmBackend {
  private readonly limiter: RateLimiter;

  constructor(
    private readonly http: HttpClient,
    private readonly config: Config,
    limiter?: RateLimiter
  ) {
    this.limiter = limiter ?? new RateLimiter(1100);
  }

  private url(profile: Profile, service: string, coords: LatLon[]): string {
    const path = coords.map((c) => `${c.lon},${c.lat}`).join(';');
    // The inner `driving` segment is intentional — see PROFILE_PREFIX.
    return `${this.config.osrmUrl}/${PROFILE_PREFIX[profile]}/${service}/v1/driving/${path}`;
  }

  async route(
    profile: Profile,
    coords: LatLon[],
    includeSteps = false
  ): Promise<OsrmRoute> {
    const params = new URLSearchParams({
      overview: 'false',
      alternatives: 'false',
      steps: includeSteps ? 'true' : 'false',
    });
    const data = expectOk(
      await this.http.request(
        'osrm',
        `${this.url(profile, 'route', coords)}?${params}`,
        this.limiter
      ),
      'route'
    );
    const raw = arrayOf(data.routes)[0];
    if (raw === undefined) throw new Error('OSRM returned no route');
    const route = shapeRoute(raw, 'route');
    return {
      distanceMeters: route.distanceMeters,
      durationSeconds: route.durationSeconds,
      legs: toLegs(route.rawLegs),
      ...(includeSteps ? { steps: toSteps(route.rawLegs) } : {}),
    };
  }

  async table(
    profile: Profile,
    origins: LatLon[],
    destinations: LatLon[]
  ): Promise<OsrmMatrix> {
    const coords = [...origins, ...destinations];
    const sources = origins.map((_, i) => i).join(';');
    const dests = destinations.map((_, i) => i + origins.length).join(';');
    const params = new URLSearchParams({
      annotations: 'duration,distance',
      sources,
      destinations: dests,
    });
    const data = expectOk(
      await this.http.request(
        'osrm',
        `${this.url(profile, 'table', coords)}?${params}`,
        this.limiter
      ),
      'table'
    );
    return {
      durations: numberMatrix(data.durations),
      distances: numberMatrix(data.distances),
    };
  }

  async trip(
    profile: Profile,
    coords: LatLon[],
    roundtrip: boolean
  ): Promise<OsrmTrip> {
    const params = new URLSearchParams({
      overview: 'false',
      steps: 'false',
      roundtrip: roundtrip ? 'true' : 'false',
      source: 'first',
      ...(roundtrip ? {} : { destination: 'last' }),
    });
    const data = expectOk(
      await this.http.request(
        'osrm',
        `${this.url(profile, 'trip', coords)}?${params}`,
        this.limiter
      ),
      'trip'
    );
    const raw = arrayOf(data.trips)[0];
    const waypoints = arrayOf(data.waypoints);
    if (raw === undefined || waypoints.length === 0) {
      throw new Error('OSRM returned no trip');
    }
    const trip = shapeRoute(raw, 'trip');
    // waypoints[i].waypoint_index is input i's position in the optimized tour;
    // invert it into "visit order" (order[k] = index of the k-th stop). The
    // tour has to name every input exactly once, or the order is not one.
    const positions = waypoints.map((wp) =>
      nonNegativeInteger(objectOf(wp)?.waypoint_index)
    );
    if (
      waypoints.length !== coords.length ||
      new Set(positions).size !== coords.length ||
      positions.some((at) => at === undefined || at >= coords.length)
    ) {
      throw new Error(
        'OSRM returned a trip whose visiting order does not cover the stops'
      );
    }
    const order = positions
      .map((at, inputIndex) => ({ inputIndex, at: at as number }))
      .toSorted((a, b) => a.at - b.at)
      .map((entry) => entry.inputIndex);
    return {
      order,
      distanceMeters: trip.distanceMeters,
      durationSeconds: trip.durationSeconds,
      legs: toLegs(trip.rawLegs),
    };
  }
}

/**
 * OSRM's envelope: an object with `code: "Ok"`. Anything it says about a
 * failure is the service's text and is quoted as such — cut, cleaned and
 * labelled — rather than concatenated into the message as it arrived.
 */
function expectOk(data: unknown, service: string): Record<string, unknown> {
  const envelope = objectOf(data);
  if (!envelope) {
    throw new Error(
      `OSRM ${service} answered with something that is not a JSON object`
    );
  }
  if (envelope.code !== 'Ok') {
    const message =
      envelope.message === undefined
        ? ''
        : `; message: ${upstreamText(envelope.message)}`;
    throw new Error(
      `OSRM ${service} failed — code: ${upstreamText(envelope.code, 40)}${message}`
    );
  }
  return envelope;
}

/**
 * The two numbers a route or trip answer cannot do without. A missing or
 * non-finite one used to become `NaN`/`Infinity` in `distance_m`, which the
 * output schema refuses — the whole call failed with a validation message
 * instead of this sentence.
 */
function shapeRoute(raw: unknown, service: string): ShapedRoute {
  const route = objectOf(raw);
  const distance = measure(route?.distance);
  const duration = measure(route?.duration);
  if (!route || distance === undefined || duration === undefined) {
    throw new Error(
      `OSRM ${service} answered without a usable distance and duration`
    );
  }
  return {
    distanceMeters: distance,
    durationSeconds: duration,
    rawLegs: arrayOf(route.legs),
  };
}

function toLegs(rawLegs: unknown[]): OsrmLeg[] {
  return rawLegs.map((raw) => {
    const leg = objectOf(raw) ?? {};
    const summary = text(leg.summary, MAX_NAME_LENGTH);
    return {
      distanceMeters: measure(leg.distance) ?? 0,
      durationSeconds: measure(leg.duration) ?? 0,
      ...(summary ? { summary } : {}),
    };
  });
}

function toSteps(rawLegs: unknown[]): OsrmStep[] {
  const steps: OsrmStep[] = [];
  for (const rawLeg of rawLegs) {
    for (const rawStep of arrayOf(objectOf(rawLeg)?.steps)) {
      const step = objectOf(rawStep) ?? {};
      const maneuver = objectOf(step.maneuver) ?? {};
      const kind = text(maneuver.type, 40) ?? '';
      const name = text(step.name, MAX_NAME_LENGTH) ?? '';
      if (kind === 'arrive' && !name) continue;
      const direction = [kind, text(maneuver.modifier, 40)]
        .filter(Boolean)
        .join(' ');
      const road = name || '(unnamed road)';
      steps.push({
        instruction: direction ? `${direction} onto ${road}` : road,
        distanceMeters: measure(step.distance) ?? 0,
      });
    }
  }
  return steps;
}
