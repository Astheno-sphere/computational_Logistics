/**
 * Measure Apify dataset propagation after a run reaches SUCCEEDED, and test
 * whether a repeated identical GET is being served from cache.
 *
 * Two pollers race on the SAME dataset from the moment the run finishes:
 *   A: the exact same URL every time (what the client did)
 *   B: the same URL plus a cache-busting parameter
 *
 * Usage: APIFY_TOKEN=... node tools/probe-lag.mjs
 */
const TOKEN = process.env.APIFY_TOKEN;
const H = { Authorization: 'Bearer ' + TOKEN };
const g = async u => { const r = await fetch(u, { headers: H }); return r.json(); };
const sleep = ms => new Promise(r => setTimeout(r, ms));

const run = (await (await fetch('https://api.apify.com/v2/acts/malonestar~karst-sinkhole-risk-screener/runs', {
  method: 'POST', headers: { ...H, 'Content-Type': 'application/json' },
  body: JSON.stringify({ assets: [{ lat: 28.5383, lon: -81.3792, label: 'Orlando, FL' }] }),
})).json()).data;
console.log('run', run.id);

let cur = run;
while (!['SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT'].includes(cur.status)) {
  await sleep(2000);
  cur = (await g(`https://api.apify.com/v2/actor-runs/${run.id}`)).data;
}
const finished = Date.now();
console.log('status', cur.status, 'dataset', cur.defaultDatasetId);

const ds = cur.defaultDatasetId;
const base = `https://api.apify.com/v2/datasets/${ds}/items?limit=200&clean=true`;
let firstA = null, firstB = null, firstMeta = null;

for (let i = 0; i < 30 && (firstA === null || firstB === null); i++) {
  const t = Date.now() - finished;
  const [a, b, meta] = await Promise.all([
    g(base),
    g(base + '&_cb=' + Date.now()),
    g(`https://api.apify.com/v2/datasets/${ds}`),
  ]);
  const la = Array.isArray(a) ? a.length : -1;
  const lb = Array.isArray(b) ? b.length : -1;
  const mc = meta.data ? meta.data.itemCount : -1;
  if (firstA === null && la > 0) firstA = t;
  if (firstB === null && lb > 0) firstB = t;
  if (firstMeta === null && mc > 0) firstMeta = t;
  console.log(`t=${String(t).padStart(6)}ms  sameUrl=${la}  cacheBusted=${lb}  itemCount=${mc}`);
  await sleep(1000);
}

console.log(`\nfirst non-empty: sameUrl=${firstA}ms  cacheBusted=${firstB}ms  itemCount>0 at ${firstMeta}ms`);
console.log(firstA !== null && firstB !== null && firstA - firstB > 3000
  ? 'VERDICT: the repeated identical GET is being served stale — cache-bust it.'
  : 'VERDICT: no meaningful cache effect; this is genuine propagation delay.');
