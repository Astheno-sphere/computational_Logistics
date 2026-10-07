/**
 * Apify API client.
 *
 * `fetch` is injected so every branch below is reachable from the offline test
 * suite. Nothing in this file may reach the network on import.
 *
 * DESIGN NOTE — why this polls instead of using run-sync-get-dataset-items:
 * the sync endpoint hands back dataset rows without an unambiguous run status,
 * so an actor that FAILED and an actor that legitimately matched nothing can
 * arrive at the caller looking identical. Both are then reported to an agent as
 * "no results", which is a confident negative the run never actually verified.
 * Polling costs one extra request and makes the distinction explicit.
 */

const API = 'https://api.apify.com/v2';

export const TERMINAL_STATES = ['SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT'];

export class ApifyError extends Error {
  constructor(message, { status = null, runId = null, retryable = false } = {}) {
    super(message);
    this.name = 'ApifyError';
    this.status = status;
    this.runId = runId;
    this.retryable = retryable;
  }
}

export function createClient({ token, fetchImpl = globalThis.fetch, sleep = ms => new Promise(r => setTimeout(r, ms)), now = () => Date.now() }) {
  if (!token) throw new ApifyError('APIFY_TOKEN is not set. Create a token at https://console.apify.com/settings/integrations and set APIFY_TOKEN in your MCP client config.');

  async function request(pathname, { method = 'GET', body, attempt = 1 } = {}) {
    const res = await fetchImpl(API + pathname, {
      method,
      headers: {
        Authorization: 'Bearer ' + token,
        ...(body ? { 'Content-Type': 'application/json' } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });

    // 429 and 5xx are transient. Everything else is an answer, including 4xx.
    if (res.status === 429 || res.status >= 500) {
      if (attempt >= 4) {
        throw new ApifyError(`Apify API ${method} ${pathname} failed with HTTP ${res.status} after ${attempt} attempts. This is an Apify platform problem, not a data problem — no conclusion should be drawn about the underlying government source.`, { status: res.status, retryable: true });
      }
      await sleep(500 * 2 ** (attempt - 1));
      return request(pathname, { method, body, attempt: attempt + 1 });
    }

    let json = null;
    const text = await res.text();
    try { json = text ? JSON.parse(text) : null; } catch {
      throw new ApifyError(`Apify API ${method} ${pathname} returned HTTP ${res.status} with a non-JSON body (first 200 chars: ${text.slice(0, 200)}).`, { status: res.status });
    }

    if (!res.ok) {
      const detail = json && json.error ? `${json.error.type}: ${json.error.message}` : `HTTP ${res.status}`;
      throw new ApifyError(`Apify API ${method} ${pathname} failed — ${detail}`, { status: res.status });
    }

    // TWO ENVELOPE SHAPES, and assuming one costs you the other silently.
    // Most Apify v2 endpoints wrap their payload as { data: ... }, but
    // /datasets/<id>/items returns a BARE JSON ARRAY. Reading `.data` off that
    // array yields undefined, which downstream reads as "no rows" — a confident
    // empty result produced by a request that actually succeeded. Measured
    // 2026-08-11: this made every dataset read return [] forever while the
    // dataset's own itemCount correctly reported 1.
    if (Array.isArray(json)) return json;
    return json && Object.prototype.hasOwnProperty.call(json, 'data') ? json.data : json;
  }

  /**
   * Read a dataset that has just been written, without believing an early zero.
   *
   * MEASURED 2026-08-11: a karst screener run reached SUCCEEDED, the dataset read
   * one millisecond later returned [], and the same dataset held 1 row (65 fields,
   * in_karst_terrain: true) moments afterwards. Both `itemCount` and the items
   * endpoint lag the run's terminal state, and they lag TOGETHER — so a single
   * sample is not evidence. Reporting that first read would have told the caller
   * the source "genuinely matched nothing" about a site that is in carbonate karst.
   *
   * The delay is INTERMITTENT, not a fixed cost: measured on the same actor and
   * the same dataset endpoint, one run was readable 0 ms after finishing and
   * another was still unreadable at 21 s while its own itemCount already said 1.
   * A cache-busting parameter made no difference, so this is genuine propagation,
   * not a stale edge cache. Hence a generous ceiling — a premature give-up wastes
   * a run the caller has already paid for.
   *
   * A zero is only accepted after `minReads` independent reads spanning at least
   * `minWindowMs`, all of which agreed that both signals were zero.
   */
  async function settleDataset(datasetId, maxItems, { minReads = 3, minWindowMs = 4000, maxWaitMs = 60000, gapMs = 2000 } = {}) {
    const started = now();
    let reads = 0;
    let lastCount = 0;
    while (true) {
      const [meta, items] = await Promise.all([
        request(`/datasets/${datasetId}`),
        request(`/datasets/${datasetId}/items?limit=${maxItems}&clean=true`),
      ]);
      const rows = Array.isArray(items) ? items : [];
      // Take the max of both signals; either one being non-zero disproves "empty".
      lastCount = Math.max(rows.length, (meta && meta.itemCount) || 0);
      reads += 1;
      if (rows.length > 0) return { ok: true, items: rows };

      const elapsed = now() - started;
      if (lastCount === 0 && reads >= minReads && elapsed >= minWindowMs) {
        return { ok: true, items: [] };
      }
      if (elapsed >= maxWaitMs) {
        if (lastCount > 0) {
          return {
            ok: false,
            message: `The run SUCCEEDED and its dataset reports ${lastCount} row(s), but the rows were still not readable after ${Math.round(elapsed / 1000)}s. This is an Apify dataset-propagation delay, not an empty result — retry the call, or read the dataset directly. No conclusion should be drawn about the underlying source.`,
          };
        }
        return { ok: true, items: [] };
      }
      await sleep(gapMs);
    }
  }

  return {
    request,

    /**
     * Start a run, wait for a terminal state, and return rows.
     * Resolves with { status, runId, items, itemCount, datasetId, statusMessage }.
     * A non-SUCCEEDED terminal state RESOLVES rather than throwing so the caller
     * can report the distinction between "failed" and "matched nothing" verbatim.
     */
    async runActor(actorId, input, { waitSecs = 300, pollMs = 2000, maxItems = 200 } = {}) {
      const slug = actorId.replace('/', '~');
      const run = await request(`/acts/${slug}/runs`, { method: 'POST', body: input });
      const runId = run.id;

      const deadline = now() + waitSecs * 1000;
      let status = run.status;
      let current = run;
      while (!TERMINAL_STATES.includes(status)) {
        if (now() > deadline) {
          return {
            status: 'CLIENT_TIMEOUT',
            runId,
            items: [],
            itemCount: 0,
            datasetId: current.defaultDatasetId || null,
            statusMessage: `The run did not reach a terminal state within ${waitSecs}s. It is still running on Apify — check https://console.apify.com/actors/runs/${runId}. No result is available yet; this is NOT evidence that the source returned nothing.`,
          };
        }
        await sleep(pollMs);
        current = await request(`/actor-runs/${runId}`);
        status = current.status;
      }

      const datasetId = current.defaultDatasetId;
      if (status !== 'SUCCEEDED') {
        return {
          status,
          runId,
          items: [],
          itemCount: 0,
          datasetId,
          statusMessage: `The run terminated with status ${status}${current.statusMessage ? ` — ${current.statusMessage}` : ''}. These actors are built to fail loudly rather than emit a misleading empty result, so treat this as "the question was not answered", never as "nothing was found".`,
        };
      }

      const settled = await settleDataset(datasetId, maxItems);
      if (!settled.ok) {
        return {
          status: 'DATASET_UNSETTLED',
          runId,
          items: [],
          itemCount: 0,
          datasetId,
          statusMessage: settled.message,
        };
      }
      const rows = settled.items;
      return {
        status,
        runId,
        items: rows,
        itemCount: rows.length,
        datasetId,
        statusMessage: rows.length === 0
          ? 'The run SUCCEEDED and the actor emitted zero rows. For these actors that is a real answer — the query was well-formed, the source was reached, and it genuinely matched nothing.'
          : null,
      };
    },
  };
}
