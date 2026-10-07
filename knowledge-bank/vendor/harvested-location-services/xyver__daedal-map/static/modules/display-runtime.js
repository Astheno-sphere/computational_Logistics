/**
 * Lightweight browser-display capability and tab-lifecycle intelligence.
 *
 * This controls interactive display budgets only. MCP/query limits belong to
 * the server tool contract and must never be inferred from browser hardware.
 */

const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '0.0.0.0', '::1', '[::1]']);

export function isLocalDisplayHost(hostname) {
  return LOCAL_HOSTS.has(String(hostname || '').trim().toLowerCase());
}

export function selectDisplayProfile({
  hostname = '',
  deviceMemory = null,
  hardwareConcurrency = null,
  saveData = false,
  effectiveType = ''
} = {}) {
  const local = isLocalDisplayHost(hostname);
  const memory = Number(deviceMemory);
  const cores = Number(hardwareConcurrency);
  const explicitlySmallDevice = (Number.isFinite(memory) && memory > 0 && memory <= 4)
    || (Number.isFinite(cores) && cores > 0 && cores <= 2);
  const constrainedNetwork = Boolean(saveData)
    || ['slow-2g', '2g', '3g'].includes(String(effectiveType || '').toLowerCase());

  if (local && !explicitlySmallDevice) return 'localPower';
  if (!constrainedNetwork && memory >= 8 && cores >= 8) return 'hostedEnhanced';
  return 'hostedSafe';
}

function currentEnvironment() {
  const connection = typeof navigator !== 'undefined' ? navigator.connection : null;
  return {
    hostname: typeof window !== 'undefined' ? window.location?.hostname : '',
    deviceMemory: typeof navigator !== 'undefined' ? navigator.deviceMemory : null,
    hardwareConcurrency: typeof navigator !== 'undefined' ? navigator.hardwareConcurrency : null,
    saveData: Boolean(connection?.saveData),
    effectiveType: String(connection?.effectiveType || '')
  };
}

export const DisplayRuntime = {
  initialized: false,
  profileName: 'hostedSafe',
  hiddenAt: null,
  lastHiddenDurationMs: 0,
  longTaskCount: 0,
  longTaskDurationMs: 0,
  observer: null,
  callbacks: null,

  init(callbacks = {}) {
    if (this.initialized) return this.getSnapshot();
    this.initialized = true;
    this.callbacks = callbacks;
    this.profileName = selectDisplayProfile(currentEnvironment());

    if (typeof document !== 'undefined') {
      if (document.hidden) this.hiddenAt = Date.now();
      document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
          this.hiddenAt = Date.now();
          this.callbacks?.onHidden?.(this.getSnapshot());
          window.dispatchEvent(new CustomEvent('daedalmap-display-hidden', { detail: this.getSnapshot() }));
          return;
        }
        this.lastHiddenDurationMs = this.hiddenAt == null ? 0 : Math.max(0, Date.now() - this.hiddenAt);
        this.hiddenAt = null;
        this.callbacks?.onVisible?.(this.getSnapshot());
        window.dispatchEvent(new CustomEvent('daedalmap-display-visible', { detail: this.getSnapshot() }));
      });
    }

    if (typeof PerformanceObserver !== 'undefined') {
      try {
        this.observer = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            this.longTaskCount += 1;
            this.longTaskDurationMs += Number(entry.duration || 0);
          }
        });
        this.observer.observe({ type: 'longtask', buffered: true });
      } catch (_error) {
        this.observer = null;
      }
    }

    return this.getSnapshot();
  },

  getSnapshot() {
    const environment = currentEnvironment();
    const heap = typeof performance !== 'undefined' ? performance.memory : null;
    return {
      profileName: this.profileName,
      localDisplay: isLocalDisplayHost(environment.hostname),
      visible: typeof document === 'undefined' ? true : !document.hidden,
      wasDiscarded: typeof document === 'undefined' ? false : Boolean(document.wasDiscarded),
      lastHiddenDurationMs: this.lastHiddenDurationMs,
      longTaskCount: this.longTaskCount,
      longTaskDurationMs: Math.round(this.longTaskDurationMs),
      deviceMemoryGiB: environment.deviceMemory,
      hardwareConcurrency: environment.hardwareConcurrency,
      saveData: environment.saveData,
      effectiveType: environment.effectiveType || null,
      jsHeapUsedBytes: Number(heap?.usedJSHeapSize || 0) || null,
      jsHeapLimitBytes: Number(heap?.jsHeapSizeLimit || 0) || null
    };
  }
};

