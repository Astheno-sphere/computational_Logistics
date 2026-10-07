/**
 * The published version, in one place: reported to MCP clients, sent to the API
 * in the User-Agent so adoption can be measured, and checked against
 * package.json, server.json and manifest.json by scripts/release.mjs, which
 * refuses to release if they disagree.
 */
export const VERSION = '0.1.6'
