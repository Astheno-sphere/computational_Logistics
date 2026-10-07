'use strict';

const { addLabel, VALID_VERDICTS } = require('../../feedback/store');

module.exports = {
  name: 'qa_probe_label',
  description:
    'Record feedback on an endpoint diagnosis so qa-probe reapplies it on future runs. ' +
    'Use this to teach the tool: mark a result as expected/known (suppresses the finding) ' +
    'or confirm it as a real bug. Example: "mark the empty GET /alerts result as expected".',
  inputSchema: {
    type: 'object',
    properties: {
      endpoint: { type: 'string', description: 'Endpoint key exactly as shown in the report, e.g. "GET /alerts".' },
      verdict: {
        type: 'string',
        description: `One of: ${[...VALID_VERDICTS].join(', ')}. expected/ignore/known_gate/ok SUPPRESS the finding; bug/real_bug/confirm CONFIRM it.`,
      },
      reason: { type: 'string', description: 'Why — free text. Strongly recommended; this is the audit trail.' },
      signal: {
        type: 'string',
        description: 'Optional rootCause this label applies to (e.g. "empty_db"). The label auto-revokes if the observed rootCause changes, so it can never hide a regression. Defaults to "any".',
      },
    },
    required: ['endpoint', 'verdict'],
  },
  async execute({ endpoint, verdict, reason, signal } = {}, { config }) {
    if (!config) return { ok: false, error: 'No config available.' };
    try {
      const { label, path } = addLabel(config, { endpoint, verdict, reason, by: 'ai', signal });
      return {
        ok: true,
        endpoint,
        recorded: label,
        note: label.effect === 'suppress'
          ? `Recorded. "${endpoint}" will be acknowledged (suppressed) on future runs while its result stays ${label.signal === 'any' ? 'as-is' : label.signal}. Auditable, and auto-revokes if the result changes.`
          : `Recorded. "${endpoint}" is now a confirmed issue and will be flagged with high confidence on future runs.`,
        storedAt: path,
      };
    } catch (err) {
      return { ok: false, error: err.message };
    }
  },
};
