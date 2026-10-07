/**
 * The annotation block every tool of this server carries.
 *
 * Written out rather than left to the defaults, because the defaults are not
 * neutral: the specification says `destructiveHint` and `openWorldHint` both
 * default to **true**, so an omitted field is the *stronger* claim. A tool that
 * says nothing is a destructive tool in an open world.
 *
 * `openWorldHint: true` is the one place in this family where that default is
 * also the truth, and it is worth stating for exactly that reason. The rest of
 * these servers talk to a single instance somebody configured; this one queries
 * public Nominatim, OSRM and Overpass backends over the whole planet's data,
 * which is the specification's own example of an open world.
 */
export const READ_ONLY = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: true,
} as const;
