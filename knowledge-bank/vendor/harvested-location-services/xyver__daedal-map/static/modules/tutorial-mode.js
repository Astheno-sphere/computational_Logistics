const STORAGE_KEY = 'tutorial_mode';

function safeLocalStorageGet(key) {
  try {
    return localStorage.getItem(key);
  } catch (error) {
    return null;
  }
}

function safeLocalStorageSet(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch (error) {
    // Ignore localStorage failures in restricted contexts.
  }
}

export function parseTutorialCommand(query) {
  if (!query) return null;

  const normalized = query.trim().toLowerCase();
  const hasTutorial = /\btutorial\b/.test(normalized);
  const hasUiHelp =
    /\bhelp me understand the ui\b/.test(normalized) ||
    /\bshow me what everything does\b/.test(normalized);

  if (!hasTutorial && !hasUiHelp) return null;

  if (/\b(turn|switch|set|make)\s+(the\s+)?tutorial(\s+mode)?\s+(off|disable|disabled)\b/.test(normalized)) {
    return { action: 'off' };
  }
  if (/\b(turn|switch|set|make)\s+(the\s+)?tutorial(\s+mode)?\s+(on|enable|enabled)\b/.test(normalized)) {
    return { action: 'on' };
  }
  if (/\b(enable|start|show)\s+(the\s+)?tutorial(\s+mode)?\b/.test(normalized)) {
    return { action: 'on' };
  }
  if (/\b(disable|stop|hide)\s+(the\s+)?tutorial(\s+mode)?\b/.test(normalized)) {
    return { action: 'off' };
  }
  if (/\btutorial(\s+mode)?\s+on\b/.test(normalized)) {
    return { action: 'on' };
  }
  if (/\btutorial(\s+mode)?\s+off\b/.test(normalized)) {
    return { action: 'off' };
  }
  if (/\btoggle\s+(the\s+)?tutorial(\s+mode)?\b/.test(normalized) || /\btutorial(\s+mode)?\s+toggle\b/.test(normalized)) {
    return { action: 'toggle' };
  }
  if (hasUiHelp || /\btutorial(\s+mode)?\b/.test(normalized)) {
    return { action: 'on' };
  }

  return null;
}

export const TutorialMode = {
  initialized: false,
  enabled: false,
  toggleButton: null,
  timelineRegion: null,
  timelinePanel: null,
  timelineDismissBtn: null,
  _boundDocumentClick: null,
  _boundEscapeKey: null,

  init() {
    if (this.initialized) return;
    this.timelineRegion = document.getElementById('tutorialTimelineRegion');
    this.timelinePanel = document.getElementById('tutorialTimelinePanel');
    this.timelineDismissBtn = document.getElementById('tutorialTimelineDismiss');

    this.setupRegions();
    this.restore();

    this._boundDocumentClick = (event) => this.handleDocumentClick(event);
    this._boundEscapeKey = (event) => {
      if (event.key === 'Escape') {
        this.closeAllTips();
      }
    };

    document.addEventListener('click', this._boundDocumentClick);
    document.addEventListener('keydown', this._boundEscapeKey);

    this.initialized = true;
  },

  setupRegions() {
    const regions = document.querySelectorAll('.tutorial-region');

    for (const region of regions) {
      const tip = region.querySelector('.tutorial-region-tip');
      if (!tip) continue;

      const isTimeline = region.dataset.tutorialVariant === 'timeline';
      const title = region.dataset.tutorialTitle || 'Help';
      const body = region.dataset.tutorialBody || '';

      tip.setAttribute('aria-expanded', 'false');
      tip.setAttribute('aria-label', `${title} help`);

      if (!isTimeline && !region.querySelector('.tutorial-region-tooltip')) {
        const tooltip = document.createElement('div');
        tooltip.className = 'tutorial-region-tooltip';
        tooltip.setAttribute('role', 'tooltip');
        tooltip.innerHTML = `<strong>${title}</strong><span>${body}</span>`;
        region.appendChild(tooltip);
      }

      tip.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        this.toggleRegion(region);
      });

      tip.addEventListener('mouseenter', () => {
        if (!this.enabled) return;
        if (isTimeline) {
          this.openTimelinePanel();
          return;
        }
        this.openRegion(region);
      });

      region.addEventListener('mouseleave', () => {
        if (!this.enabled) return;
        if (isTimeline) {
          this.closeTimelinePanel();
          return;
        }
        this.closeRegion(region);
      });
    }

    if (this.timelineDismissBtn) {
      this.timelineDismissBtn.addEventListener('click', (event) => {
        event.preventDefault();
        this.closeTimelinePanel();
      });
    }
  },

  restore() {
    const saved = safeLocalStorageGet(STORAGE_KEY);
    this.setTutorialMode(saved === '1', { skipSave: true });
  },

  setTutorialMode(on, options = {}) {
    this.enabled = !!on;
    document.body.classList.toggle('tutorial-mode', this.enabled);
    this.syncToggleButtons();

    if (!options.skipSave) {
      safeLocalStorageSet(STORAGE_KEY, this.enabled ? '1' : '0');
    }

    if (!this.enabled) {
      this.closeAllTips();
    }
  },

  syncToggleButtons() {
    const toggleButtons = document.querySelectorAll('#tutorialToggleBtn, [data-action="tutorial-toggle"]');
    for (const button of toggleButtons) {
      button.classList.toggle('active', this.enabled);
      button.setAttribute('aria-pressed', this.enabled ? 'true' : 'false');
      button.textContent = this.enabled ? 'Tutorial On' : 'Tutorial Off';
    }
  },

  applyCommand(action = 'toggle') {
    if (action === 'on') {
      this.setTutorialMode(true);
      return {
        enabled: true,
        message: 'Tutorial mode on. Hover or tap a help marker to see what that part of the app does.'
      };
    }

    if (action === 'off') {
      this.setTutorialMode(false);
      return {
        enabled: false,
        message: 'Tutorial mode off.'
      };
    }

    const nextEnabled = !this.enabled;
    this.setTutorialMode(nextEnabled);
    return {
      enabled: nextEnabled,
      message: nextEnabled
        ? 'Tutorial mode on. Hover or tap a help marker to see what that part of the app does.'
        : 'Tutorial mode off.'
    };
  },

  toggleRegion(region) {
    if (!this.enabled || !region) return;

    if (region.dataset.tutorialVariant === 'timeline') {
      if (this.timelinePanel?.classList.contains('visible')) {
        this.closeTimelinePanel();
      } else {
        this.openTimelinePanel();
      }
      return;
    }

    if (region.classList.contains('tutorial-region-open')) {
      this.closeRegion(region);
    } else {
      this.openRegion(region);
    }
  },

  openRegion(region) {
    if (!region) return;

    this.closeAllTips(region);
    region.classList.add('tutorial-region-open');
    const tip = region.querySelector('.tutorial-region-tip');
    if (tip) {
      tip.setAttribute('aria-expanded', 'true');
    }
  },

  closeRegion(region) {
    if (!region) return;
    region.classList.remove('tutorial-region-open');
    const tip = region.querySelector('.tutorial-region-tip');
    if (tip) {
      tip.setAttribute('aria-expanded', 'false');
    }
  },

  openTimelinePanel() {
    if (!this.timelineRegion || !this.timelinePanel) return;

    this.closeAllTips(this.timelineRegion);
    this.timelineRegion.classList.add('tutorial-region-open');
    this.timelinePanel.classList.add('visible');

    const tip = this.timelineRegion.querySelector('.tutorial-region-tip');
    if (tip) {
      tip.setAttribute('aria-expanded', 'true');
    }
  },

  closeTimelinePanel() {
    if (!this.timelineRegion || !this.timelinePanel) return;

    this.timelineRegion.classList.remove('tutorial-region-open');
    this.timelinePanel.classList.remove('visible');

    const tip = this.timelineRegion.querySelector('.tutorial-region-tip');
    if (tip) {
      tip.setAttribute('aria-expanded', 'false');
    }
  },

  closeAllTips(exceptRegion = null) {
    const openRegions = document.querySelectorAll('.tutorial-region.tutorial-region-open');
    for (const region of openRegions) {
      if (region === exceptRegion) continue;
      this.closeRegion(region);
    }

    if (this.timelineRegion && exceptRegion !== this.timelineRegion) {
      this.closeTimelinePanel();
    }
  },

  handleDocumentClick(event) {
    if (!this.enabled) return;
    if (event.target.closest('.tutorial-region')) return;
    if (event.target.closest('[data-action="tutorial-toggle"]')) return;
    this.closeAllTips();
  }
};
