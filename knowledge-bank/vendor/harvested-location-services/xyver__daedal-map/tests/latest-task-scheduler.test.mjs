import assert from 'node:assert/strict';
import test from 'node:test';

import { LatestTaskScheduler } from '../static/modules/utils/latest-task-scheduler.js';

const wait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

test('only the latest debounced task publishes', async () => {
  const scheduler = new LatestTaskScheduler();
  const published = [];
  scheduler.schedule('overlay', () => published.push('old'), { delayMs: 20 });
  scheduler.schedule('overlay', () => published.push('new'), { delayMs: 20 });
  await wait(35);
  assert.deepEqual(published, ['new']);
});

test('replacing an in-flight task aborts it and invalidates its result', async () => {
  const scheduler = new LatestTaskScheduler();
  const published = [];
  let firstSignal;
  scheduler.schedule('overlay', async ({ signal, isCurrent }) => {
    firstSignal = signal;
    await wait(25);
    if (isCurrent()) published.push('old');
  });
  await wait(5);
  scheduler.schedule('overlay', ({ isCurrent }) => {
    if (isCurrent()) published.push('new');
  });
  await wait(40);
  assert.equal(firstSignal.aborted, true);
  assert.deepEqual(published, ['new']);
});

test('different keys remain independent', async () => {
  const scheduler = new LatestTaskScheduler();
  const published = [];
  scheduler.schedule('airnow', () => published.push('airnow'), { delayMs: 10 });
  scheduler.schedule('buoys', () => published.push('buoys'), { delayMs: 10 });
  await wait(25);
  assert.deepEqual(new Set(published), new Set(['airnow', 'buoys']));
});

test('prefix cancellation tears down one provider family only', async () => {
  const scheduler = new LatestTaskScheduler();
  const published = [];
  scheduler.schedule('hurricane:atlantic', () => published.push('atlantic'), { delayMs: 15 });
  scheduler.schedule('hurricane:pacific', () => published.push('pacific'), { delayMs: 15 });
  scheduler.schedule('nws', () => published.push('nws'), { delayMs: 15 });
  scheduler.cancelPrefix('hurricane:');
  await wait(30);
  assert.deepEqual(published, ['nws']);
});
