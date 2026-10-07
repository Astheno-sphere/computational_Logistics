'use strict';

/**
 * Simple concurrency-limited async runner.
 * Runs items in batches of `concurrency` with `delayMs` between batches.
 */
async function runConcurrent(items, fn, { concurrency = 5, delayMs = 50 } = {}) {
  const results = [];
  let i = 0;

  while (i < items.length) {
    const batch = items.slice(i, i + concurrency);
    const batchResults = await Promise.all(batch.map(fn));
    results.push(...batchResults);
    i += concurrency;
    if (i < items.length && delayMs > 0) {
      await sleep(delayMs);
    }
  }

  return results;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

module.exports = { runConcurrent };
