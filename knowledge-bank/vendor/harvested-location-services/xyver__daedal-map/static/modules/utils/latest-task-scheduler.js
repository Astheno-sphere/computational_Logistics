/**
 * Keyed latest-task-wins scheduler for interactive UI work.
 *
 * Each key owns at most one debounce timer and one AbortController. Scheduling
 * a replacement cancels both, and async tasks can use isCurrent() before
 * publishing results that may have outlived their cursor position.
 */
export class LatestTaskScheduler {
  constructor() {
    this.states = new Map();
  }

  schedule(key, task, { delayMs = 0, onError = null } = {}) {
    const normalizedKey = String(key || '').trim();
    if (!normalizedKey || typeof task !== 'function') return null;
    this.cancel(normalizedKey);

    const state = { timer: null, controller: null };
    this.states.set(normalizedKey, state);
    const isCurrent = () => this.states.get(normalizedKey) === state;
    const run = async () => {
      if (!isCurrent()) return;
      state.timer = null;
      state.controller = new AbortController();
      try {
        await task({ signal: state.controller.signal, isCurrent });
      } catch (error) {
        if (error?.name !== 'AbortError') {
          if (typeof onError === 'function') onError(error);
          else console.error(`LatestTaskScheduler: task failed for ${normalizedKey}`, error);
        }
      } finally {
        if (isCurrent()) this.states.delete(normalizedKey);
      }
    };
    state.timer = setTimeout(() => { void run(); }, Math.max(0, Number(delayMs) || 0));
    return { cancel: () => this.cancel(normalizedKey), isCurrent };
  }

  cancel(key) {
    const normalizedKey = String(key || '').trim();
    const state = this.states.get(normalizedKey);
    if (!state) return;
    if (state.timer) clearTimeout(state.timer);
    state.controller?.abort?.();
    this.states.delete(normalizedKey);
  }

  cancelPrefix(prefix) {
    const normalizedPrefix = String(prefix || '');
    for (const key of [...this.states.keys()]) {
      if (key.startsWith(normalizedPrefix)) this.cancel(key);
    }
  }

  cancelAll() {
    for (const key of [...this.states.keys()]) this.cancel(key);
  }
}
