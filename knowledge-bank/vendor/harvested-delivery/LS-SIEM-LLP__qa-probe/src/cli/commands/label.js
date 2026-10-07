'use strict';

const { loadConfig } = require('../../config/loader');
const { addLabel } = require('../../feedback/store');

module.exports = function label(endpoint, verdict, opts) {
  try {
    const config = loadConfig(opts.config);
    const { label: rec, path } = addLabel(config, {
      endpoint,
      verdict,
      reason: opts.reason,
      by: opts.by || 'human',
      signal: opts.signal,
    });
    console.log(`Recorded ${rec.effect} verdict "${rec.verdict}" for ${endpoint} → ${path}`);
    if (rec.effect === 'suppress') {
      console.log(`It will be acknowledged on future runs while the result stays ${rec.signal === 'any' ? 'as-is' : rec.signal}; auto-revokes if it changes.`);
    } else {
      console.log('It will be flagged as a confirmed issue with high confidence on future runs.');
    }
    process.exit(0);
  } catch (err) {
    console.error(`Error: ${err.message}`);
    if (process.env.DEBUG) console.error(err.stack);
    process.exit(1);
  }
};
