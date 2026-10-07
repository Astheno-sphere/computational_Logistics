import type { SshTaskRunEvent } from "@unfour/command-client";

const MAX_TASK_RUN_EVENTS = 5_000;
export const MAX_CACHED_TASK_RUNS = 16;
export const MAX_CACHED_TASK_LOGS = 4;

/**
 * Append live task events while keeping transfer progress bounded. A transfer
 * can emit many updates for the same step, but the UI only needs the newest
 * snapshot to render its progress bar and transcript summary.
 */
export function appendTaskRunEvents(
  currentEvents: SshTaskRunEvent[],
  nextEvents: SshTaskRunEvent[],
) {
  const retainedNewestFirst: SshTaskRunEvent[] = [];
  const seenTransferSteps = new Set<string>();
  const merged = [...currentEvents, ...nextEvents];

  for (let index = merged.length - 1; index >= 0; index -= 1) {
    const event = merged[index]!;
    if (event.kind === "transfer" && event.stepId) {
      if (seenTransferSteps.has(event.stepId)) continue;
      seenTransferSteps.add(event.stepId);
    }
    retainedNewestFirst.push(event);
  }

  return retainedNewestFirst.reverse().slice(-MAX_TASK_RUN_EVENTS);
}

/**
 * Append a mixed batch of live events while bounding the number of run ids
 * retained by the page. Object insertion order acts as a small LRU: a run is
 * deleted and reinserted whenever fresh events arrive.
 */
export function appendTaskRunEventCache(
  current: Record<string, SshTaskRunEvent[]>,
  events: SshTaskRunEvent[],
  pinnedRunId: string | null = null,
) {
  const next = { ...current };
  const eventsByRun = new Map<string, SshTaskRunEvent[]>();
  for (const event of events) {
    const runEvents = eventsByRun.get(event.runId);
    if (runEvents) runEvents.push(event);
    else eventsByRun.set(event.runId, [event]);
  }
  for (const [runId, runEvents] of eventsByRun) {
    const retained = appendTaskRunEvents(next[runId] ?? [], runEvents);
    delete next[runId];
    next[runId] = retained;
  }
  return pruneOldestRecordEntries(next, MAX_CACHED_TASK_RUNS, pinnedRunId);
}

/** Cache only a few history logs; each backend response can be up to 2 MiB. */
export function cacheTaskRunLog(
  current: Record<string, string>,
  runId: string,
  log: string,
) {
  const next = { ...current };
  delete next[runId];
  next[runId] = log;
  return pruneOldestRecordEntries(next, MAX_CACHED_TASK_LOGS, runId);
}

export function removeTaskRunEventsForTask(
  current: Record<string, SshTaskRunEvent[]>,
  taskId: string,
) {
  return Object.fromEntries(
    Object.entries(current).filter(
      ([, events]) => !events.some((event) => event.taskId === taskId),
    ),
  );
}

function pruneOldestRecordEntries<T>(
  record: Record<string, T>,
  maxEntries: number,
  pinnedId: string | null,
) {
  const keys = Object.keys(record);
  while (keys.length > maxEntries) {
    const removableIndex = keys.findIndex((key) => key !== pinnedId);
    if (removableIndex < 0) break;
    const [removable] = keys.splice(removableIndex, 1);
    delete record[removable];
  }
  return record;
}
