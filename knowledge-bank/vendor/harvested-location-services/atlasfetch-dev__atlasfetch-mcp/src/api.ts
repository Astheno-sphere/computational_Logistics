/**
 * Thin client for the AtlasFetch HTTP API.
 *
 * Holds no data and makes no decisions about geometry — it forwards requests and
 * turns failures into sentences an assistant can act on. A raw "402" tells a
 * model nothing; "monthly allowance exhausted, resets at the start of the next
 * period" tells it to stop retrying and say so.
 */

import { VERSION } from './version.js'

const DEFAULT_BASE_URL = 'https://api.atlasfetch.xyz'

/**
 * Identifies this server to the API so adoption can be measured. The API keeps
 * only `atlasfetch-mcp/<version>` from it — never the rest, and never anything
 * about the user. See src/lib/clientId.ts in the API.
 */
export const USER_AGENT = `atlasfetch-mcp/${VERSION} (+https://github.com/atlasfetch-dev/atlasfetch-mcp)`

export function baseUrl(): string {
  return (process.env.ATLASFETCH_API_URL ?? DEFAULT_BASE_URL).replace(/\/+$/, '')
}

/** A failure the caller should be told about verbatim, not retried blindly. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    /** Whether retrying the identical request could plausibly succeed later. */
    readonly retryable: boolean = false,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

let cachedDemoKey: string | null = null

/**
 * The key every request uses.
 *
 * `ATLASFETCH_API_KEY` if set; otherwise the shared public demo key, fetched
 * once. The demo key belongs to ONE communal account whose quota, rate limit
 * and single boundary set are pooled across every anonymous user on the
 * internet — fine for a first look, wrong for anything real. `usingDemoKey`
 * exists so every tool result can say so rather than letting someone build on
 * it unawares.
 */
export async function resolveKey(): Promise<string> {
  const configured = process.env.ATLASFETCH_API_KEY?.trim()
  if (configured) return configured

  if (cachedDemoKey) return cachedDemoKey

  const response = await fetch(`${baseUrl()}/demo/key`, { headers: { 'User-Agent': USER_AGENT } })
  if (!response.ok) {
    throw new ApiError(
      'No ATLASFETCH_API_KEY is configured and the public demo key could not be fetched. ' +
        'Create a key at https://atlasfetch.xyz/dashboard and set ATLASFETCH_API_KEY.',
      response.status,
    )
  }
  const body = (await response.json()) as { key?: string }
  if (!body.key) {
    throw new ApiError('The demo key endpoint returned no key.', 502)
  }
  cachedDemoKey = body.key
  return cachedDemoKey
}

export function usingDemoKey(): boolean {
  return !process.env.ATLASFETCH_API_KEY?.trim()
}

/** One line appended to every result while the shared key is in use. */
export const DEMO_KEY_NOTICE =
  'Note: using the shared public demo key. Its quota and rate limit are pooled across ' +
  'every anonymous user, so it is unsuitable for production. Create your own at ' +
  'https://atlasfetch.xyz/dashboard and set ATLASFETCH_API_KEY.'

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { error?: string }
    return body.error ?? response.statusText
  } catch {
    return response.statusText
  }
}

/**
 * Perform a request against the API, mapping each documented failure to an
 * explanation. Status codes come from https://api.atlasfetch.xyz/openapi.json
 */
export async function request<T>(
  path: string,
  init: { method?: string; body?: unknown; query?: Record<string, string | undefined> } = {},
): Promise<T> {
  const key = await resolveKey()
  const url = new URL(`${baseUrl()}${path}`)
  for (const [name, value] of Object.entries(init.query ?? {})) {
    if (value !== undefined) url.searchParams.set(name, value)
  }

  const response = await fetch(url, {
    method: init.method ?? 'GET',
    headers: {
      Authorization: `Bearer ${key}`,
      'User-Agent': USER_AGENT,
      ...(init.body === undefined ? {} : { 'Content-Type': 'application/json' }),
    },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  })

  if (response.ok) return (await response.json()) as T

  const detail = await readError(response)
  switch (response.status) {
    case 400:
      throw new ApiError(`The request was rejected: ${detail}`, 400)
    case 401:
      throw new ApiError(
        `The API key was rejected (${detail}). Check ATLASFETCH_API_KEY, or create a new key at ` +
          'https://atlasfetch.xyz/dashboard — keys are shown once and stored hashed.',
        401,
      )
    case 402:
      throw new ApiError(
        `The monthly lookup allowance is exhausted (${detail}). It resets at the start of the next ` +
          'billing period; retrying before then will fail the same way.',
        402,
      )
    case 403:
      throw new ApiError(`The current plan does not allow this, or a cap was exceeded: ${detail}`, 403)
    case 404:
      throw new ApiError(detail || 'Not found.', 404)
    case 409:
      throw new ApiError(detail || 'Conflict — something of that name already exists.', 409)
    case 429: {
      const retryAfter = response.headers.get('retry-after')
      throw new ApiError(
        `Rate limited${retryAfter ? `; retry after ${retryAfter}s` : ''}. The limit is per key, per second.`,
        429,
        true,
      )
    }
    default:
      throw new ApiError(`AtlasFetch returned ${response.status}: ${detail}`, response.status, response.status >= 500)
  }
}

// ── Response shapes ──────────────────────────────────────────────────────────
// Only what the tools actually read. The API is the authority on the rest.

export interface LayerHit {
  code: string | null
  name: string
}

/**
 * One street answer. The lookup returns exactly three of these when `street` is
 * asked for — for 5 m, 20 m and unlimited, in that order.
 */
export interface StreetAnswer {
  /** 5, 20, or null for unlimited. */
  radiusMeters: number | null
  /** A string, never a number: `44A`, `12-14`. Only when an address matched. */
  streetNumber: string | null
  streetName: string | null
  postcode: string | null
  distanceMeters: number | null
}

export interface LookupResponse {
  /**
   * `country`, `region` and `municipal` are a single hit or null; `street` is
   * three answers, or null when there is no street data for the point's country.
   * Those two nulls mean different things — see the tool description.
   */
  base: Record<string, LayerHit | StreetAnswer[] | null>
  sets: Record<string, Array<{ name: string; properties?: unknown }>>
  encoded?: { h3?: string; pluscode?: string }
  /** Always present, empty or not. Per-set problems appear here WITH a 200. */
  errors: Array<{ type: 'access' | 'usage'; message: string }>
}

/**
 * Shape confirmed against the live API on 2026-09-16, not guessed from the
 * OpenAPI spec — the spec lists a subset of these fields, and an OpenAPI object
 * is open by default, so it is incomplete rather than wrong.
 */
export interface BoundarySet {
  id?: string
  name: string
  available?: boolean
  boundaryCount?: number
  /** Keys allowed to query this set — id AND label, not bare ids. */
  grantedKeys?: Array<{ id: string; label: string }>
  createdAt?: string
  updatedAt?: string
}
