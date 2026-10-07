import assert from 'node:assert/strict';
import test from 'node:test';

import { selectTimelineFrame } from '../static/modules/utils/timeline-frame-selection.js';

const frames = [
  { id: 'first', start_at: '2026-09-07T00:00:00Z', end_at: '2026-09-07T01:00:00Z' },
  { id: 'second', start_at: '2026-09-07T01:00:00Z', end_at: '2026-09-07T02:00:00Z' },
  { id: 'latest', start_at: '2026-09-07T03:00:00Z', end_at: null },
];

test('selects the latest frame whose retained interval contains the cursor', () => {
  assert.equal(selectTimelineFrame(frames, Date.parse('2026-09-07T00:30:00Z'))?.id, 'first');
  assert.equal(selectTimelineFrame(frames, Date.parse('2026-09-07T01:00:00Z'))?.id, 'second');
  assert.equal(selectTimelineFrame(frames, Date.parse('2026-09-08T00:00:00Z'))?.id, 'latest');
});

test('returns no frame before history or inside a retained gap', () => {
  assert.equal(selectTimelineFrame(frames, Date.parse('2026-09-06T23:00:00Z')), null);
  assert.equal(selectTimelineFrame(frames, Date.parse('2026-09-07T02:30:00Z')), null);
});
