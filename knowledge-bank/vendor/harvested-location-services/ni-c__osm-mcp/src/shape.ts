/**
 * Shaping what a backend answered before it reaches an output schema.
 *
 * Every backend response used to be cast — `(await request()) as RawRoute` —
 * and read as if the cast were a check. It is not: JSON `1e999` parses to
 * `Infinity`, a missing `distance` rounds to `NaN`, an Overpass mirror can
 * put an object where a tag value belongs, and a `display_name` can be a
 * number. Each of those reached a field the output schema types as
 * `z.number()` or `z.string()`, and the SDK answers a schema violation with an
 * error result for the *whole* call — so one malformed element in a listing
 * of twenty-five took the listing down.
 *
 * The rule these helpers enforce: a number is only a number when it is finite,
 * a string is only a string when it is one, and both have a length. Anything
 * else is `undefined`, and the caller decides whether that means "skip this
 * element" (a POI without coordinates) or "answer with a sentence" (a route
 * without a distance).
 */

/** The longest name, label or road summary a result carries. */
export const MAX_NAME_LENGTH = 500;
/** The longest turn instruction a result carries. */
export const MAX_INSTRUCTION_LENGTH = 300;
/** OSM's own ceiling on a tag key or value. */
export const MAX_TAG_KEY_LENGTH = 255;
/** Tag values: the budget poi_details and find_nearby_pois already used. */
export const MAX_TAG_VALUE_LENGTH = 500;

/**
 * A finite number, or nothing. Strings are not coerced: Nominatim sends
 * coordinates as strings and converts them explicitly, everything else that
 * sends a string where a number belongs is answering a different question.
 * `+ 0` turns `-0` into `0`, which otherwise serialises differently in the
 * two result channels.
 */
export function finiteNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value)
    ? value + 0
    : undefined;
}

/** A finite number parsed from a string the backend wrote, or nothing. */
export function finiteNumberFromText(value: unknown): number | undefined {
  if (typeof value === 'number') return finiteNumber(value);
  if (typeof value !== 'string' || value.length === 0 || value.length > 40) {
    return undefined;
  }
  return finiteNumber(Number(value));
}

/**
 * Ceiling on a distance in metres or a duration in seconds. Earth's
 * circumference is 4 × 10⁷ m; 10¹² is a thousand times a trip to the Moon,
 * or thirty thousand years. What matters is that `Math.round` of anything
 * below it is a safe integer, which `z.number().int()` insists on — the
 * property test found `-9007199254740992` on its first run.
 */
const MAX_MEASURE = 1e12;

/** A distance or duration: finite, not negative, and within {@link MAX_MEASURE}. */
export function measure(value: unknown): number | undefined {
  const n = finiteNumber(value);
  return n !== undefined && n >= 0 && n <= MAX_MEASURE ? n : undefined;
}

/** A non-negative integer the backend could mean as an id or an index. */
export function nonNegativeInteger(value: unknown): number | undefined {
  const n = finiteNumber(value);
  return n !== undefined && Number.isSafeInteger(n) && n >= 0 ? n : undefined;
}

/**
 * A string, cut to `max` characters with a visible mark. Anything that is not
 * a string is nothing — a caller that wants "5" for `5` says so with
 * {@link textOrPrimitive}.
 */
export function text(value: unknown, max: number): string | undefined {
  if (typeof value !== 'string') return undefined;
  return truncate(value, max);
}

/**
 * A string as {@link text}, but a number or boolean becomes its spelling — an
 * OSM tag value is always a string, and a mirror that sends `ele: 250` meant
 * the string.
 */
export function textOrPrimitive(
  value: unknown,
  max: number
): string | undefined {
  if (typeof value === 'number' || typeof value === 'boolean') {
    return truncate(String(value), max);
  }
  return text(value, max);
}

export function truncate(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max)}… (truncated)` : value;
}

/** An array, or an empty one. */
export function arrayOf(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

/**
 * A matrix of measures or nulls, as OSRM's `table` and ORS's `matrix`
 * answer: a cell that is not a measure is `null` — "no route", which is what
 * the output schema allows and what a caller can act on.
 */
export function numberMatrix(value: unknown): (number | null)[][] {
  return arrayOf(value).map((row) =>
    arrayOf(row).map((cell) => measure(cell) ?? null)
  );
}

/** A plain object, or nothing. */
export function objectOf(value: unknown): Record<string, unknown> | undefined {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

/**
 * An OSM tag set: string keys to string values, both bounded. Keys and values
 * that are not strings (or a number/boolean spelled as one) are dropped —
 * there is no tag they could have been.
 *
 * Built with `Object.fromEntries`, which defines every key as an own property:
 * a mapper can name a tag `__proto__`, and an assignment `tags[key] = value`
 * would silently set the prototype instead of the tag.
 */
export function stringTags(value: unknown): Record<string, string> {
  const source = objectOf(value);
  if (!source) return {};
  const entries: Array<[string, string]> = [];
  for (const [key, entry] of Object.entries(source)) {
    const cleanValue = textOrPrimitive(entry, MAX_TAG_VALUE_LENGTH);
    if (key.length === 0 || cleanValue === undefined) continue;
    entries.push([truncate(key, MAX_TAG_KEY_LENGTH), cleanValue]);
  }
  return Object.fromEntries(entries);
}
