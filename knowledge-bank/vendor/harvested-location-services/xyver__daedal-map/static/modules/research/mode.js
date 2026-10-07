/**
 * Workflow mode toggle for the chat panel.
 */

import { postMsgpack } from '../utils/fetch.js';
import { getApiUrl } from '../chat/api.js';
import { isSharedShellRoute } from '../routing/app-route-state.js';

export class ResearchModeToggle {
  static SHOW_CATALOG_SURFACE_CONTROLS = false;

  constructor({
    container,
    getSessionId,
    onModeChange,
    onLoadCorpus,
    onSelectCorpus,
    onSaveCorpus,
    onSyncCorpus,
    onRemoveBrowserCopy,
    onCatalogSurfaceChange
  }) {
    this.container = container;
    this.getSessionId = getSessionId;
    this.onModeChange = onModeChange;
    this.onLoadCorpus = onLoadCorpus;
    this.onSelectCorpus = onSelectCorpus;
    this.onSaveCorpus = onSaveCorpus;
    this.onSyncCorpus = onSyncCorpus;
    this.onRemoveBrowserCopy = onRemoveBrowserCopy;
    this.onCatalogSurfaceChange = onCatalogSurfaceChange;
    this.mode = 'explore';
    this.catalogSurface = 'published';
    this.canUseCatalogSurface = false;
    this.buttons = {};
    this.surfaceButtons = {};
    this.corpusOptions = [];
    this.selectedCorpusId = '';
    this.controls = {};
    this.loadedCorpusId = '';
    this.hasActiveArtifacts = false;
    this.hasStaleArtifacts = false;
    this.optionsLoading = false;
    this.optionsLoadingLabel = 'Loading saved corpora...';
    this.modeMount = null;
  }

  static MODES = ['explore', 'research', 'ops'];

  init() {
    if (!this.container) return;

    const mount = document.getElementById('mapModeMount') || document.getElementById('sidebarModeMount');
    this.modeMount = mount;
    const corpusMount = document.getElementById('sidebarResearchMount');
    const wrap = document.createElement('div');
    wrap.className = 'chat-mode-toggle chat-mode-toggle--header';
    const surfaceControls = this.createCatalogSurfaceControls();
    const corpusControls = this.createCorpusControls();

    wrap.appendChild(this.createToggleButtons());
    if (mount) {
      mount.classList.add('chat-mode-toggle-host');
      mount.replaceChildren(wrap, surfaceControls);
    } else {
      this.container.insertBefore(wrap, this.container.firstChild);
      this.container.insertBefore(surfaceControls, wrap);
    }
    if (corpusMount) {
      corpusMount.replaceChildren(corpusControls);
    } else if (this.container) {
      this.container.insertBefore(corpusControls, this.container.firstChild);
    }
    this.updateActive();
  }

  createToggleButtons() {
    const group = document.createElement('div');
    group.className = 'chat-mode-toggle__group';

    for (const mode of ResearchModeToggle.MODES) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chat-mode-toggle__btn';
      btn.dataset.mode = mode;
      btn.textContent = this.getModeLabel(mode);
      btn.addEventListener('click', async () => {
        if (this.mode === mode) return;
        this.mode = mode;
        this.updateActive();
        await this.onModeChange?.(this.mode);
      });
      this.buttons[mode] = btn;
      group.appendChild(btn);
    }

    return group;
  }

  createCatalogSurfaceControls() {
    const wrap = document.createElement('div');
    wrap.className = 'chat-mode-toggle__surface chat-mode-toggle__surface--floating';
    wrap.hidden = true;

    const label = document.createElement('span');
    label.className = 'chat-mode-toggle__surface-label';
    label.textContent = 'Catalog';
    wrap.appendChild(label);

    const group = document.createElement('div');
    group.className = 'chat-mode-toggle__surface-group';

    const surfaces = [
      { id: 'published', label: 'Live' },
      { id: 'wip', label: 'WIP' }
    ];
    for (const surface of surfaces) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chat-mode-toggle__surface-btn';
      btn.dataset.surface = surface.id;
      btn.textContent = surface.label;
      btn.addEventListener('click', async () => {
        if (this.catalogSurface === surface.id) return;
        this.catalogSurface = surface.id;
        this.updateActive();
        await this.onCatalogSurfaceChange?.(surface.id);
      });
      this.surfaceButtons[surface.id] = btn;
      group.appendChild(btn);
    }

    wrap.appendChild(group);
    this.controls.surfaceWrap = wrap;
    return wrap;
  }

  createCorpusControls() {
    const controls = document.createElement('div');
    controls.className = 'chat-mode-toggle__corpus hidden';

    const select = document.createElement('select');
    select.className = 'chat-mode-toggle__select';
    select.disabled = true;
    select.addEventListener('change', async () => {
      this.selectedCorpusId = select.value || '';
      await this.onSelectCorpus?.(this.selectedCorpusId);
    });

    const loadBtn = document.createElement('button');
    loadBtn.type = 'button';
    loadBtn.className = 'chat-mode-toggle__load';
    loadBtn.textContent = 'Load Data';
    loadBtn.disabled = true;
    loadBtn.addEventListener('click', async () => {
      if (!this.selectedCorpusId) return;
      await this.onLoadCorpus?.(this.selectedCorpusId);
    });

    const status = document.createElement('div');
    status.className = 'chat-mode-toggle__status';
    status.textContent = 'Select a saved corpus to begin.';

    controls.appendChild(select);
    controls.appendChild(loadBtn);
    controls.appendChild(status);

    this.controls.wrap = controls;
    this.controls.select = select;
    this.controls.loadBtn = loadBtn;
    this.controls.status = status;
    this.renderCorpusOptions();
    return controls;
  }

  updateActive() {
    this.updateRouteVisibility();
    const selectedValue = this.controls.select?.value || this.selectedCorpusId || '';
    const canLoad = Boolean(selectedValue);
    const alreadyLoaded = Boolean(
      selectedValue
      && this.loadedCorpusId
      && selectedValue === this.loadedCorpusId
      && this.hasActiveArtifacts
      && !this.hasStaleArtifacts
    );
    this.selectedCorpusId = selectedValue;
    const title = document.getElementById('sidebarModeTitle');
    if (title) {
      title.textContent = this.getModeTitle(this.mode);
    }
    for (const mode of ResearchModeToggle.MODES) {
      const btn = this.buttons[mode];
      if (!btn) continue;
      const isActive = this.mode === mode;
      btn.classList.toggle('active', isActive);
      btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      btn.title = isActive ? `${this.getModeTitle(mode)} active` : `Switch to ${this.getModeTitle(mode)}`;
    }
    if (this.controls.surfaceWrap) {
      const showSurfaceControls = ResearchModeToggle.SHOW_CATALOG_SURFACE_CONTROLS && this.canUseCatalogSurface;
      this.controls.surfaceWrap.hidden = !showSurfaceControls;
      this.controls.surfaceWrap.classList.toggle('hidden', !showSurfaceControls);
    }
    for (const [surface, btn] of Object.entries(this.surfaceButtons || {})) {
      const isActive = this.catalogSurface === surface;
      btn.classList.toggle('active', isActive);
      btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    }
    if (this.controls.wrap) {
      const hideCorpusControls = this.mode !== 'research';
      this.controls.wrap.classList.toggle('hidden', hideCorpusControls);
      this.controls.wrap.hidden = hideCorpusControls;
      this.controls.wrap.setAttribute('aria-hidden', hideCorpusControls ? 'true' : 'false');
    }
    if (this.controls.loadBtn) {
      this.controls.loadBtn.disabled = !canLoad || this.controls.loadBtn.dataset.loading === 'true' || alreadyLoaded;
      this.controls.loadBtn.textContent = this.controls.loadBtn.dataset.loading === 'true'
        ? 'Loading...'
        : (alreadyLoaded ? 'Loaded' : 'Load Data');
    }
  }

  updateRouteVisibility() {
    if (!this.modeMount) return;
    const showModeSelector = isSharedShellRoute();
    this.modeMount.hidden = !showModeSelector;
    this.modeMount.setAttribute('aria-hidden', showModeSelector ? 'false' : 'true');
    this.modeMount.classList.toggle('hidden', !showModeSelector);
  }

  getModeLabel(mode) {
    return mode === 'research' ? 'Research' : mode === 'ops' ? 'Ops' : 'Explore';
  }

  getModeTitle(mode) {
    return mode === 'research' ? 'Research Mode' : mode === 'ops' ? 'Ops Mode' : 'Explore Mode';
  }

  async snapshotCorpus() {
    return await postMsgpack(getApiUrl('/api/research/corpus'), {
      sessionId: this.getSessionId?.()
    });
  }

  setCorpusOptions(options = [], selectedId = '') {
    this.corpusOptions = Array.isArray(options) ? options : [];
    this.selectedCorpusId = selectedId || '';
    this.renderCorpusOptions();
    this.updateActive();
  }

  setSelectedCorpusId(selectedId = '') {
    this.selectedCorpusId = selectedId || '';
    if (this.controls.select) {
      const hasOption = Array.from(this.controls.select.options || []).some(option => option.value === this.selectedCorpusId);
      this.controls.select.value = hasOption ? this.selectedCorpusId : '';
    }
    this.updateActive();
  }

  setCorpusStatus(message = '') {
    if (this.controls.status) {
      this.controls.status.textContent = message || '';
    }
  }

  setCorpusLoading(isLoading) {
    if (!this.controls.loadBtn) return;
    const selectedValue = this.controls.select?.value || this.selectedCorpusId || '';
    this.selectedCorpusId = selectedValue;
    this.controls.loadBtn.dataset.loading = isLoading ? 'true' : 'false';
    this.controls.loadBtn.textContent = isLoading ? 'Loading...' : 'Load Data';
    this.controls.loadBtn.disabled = isLoading || !selectedValue;
    if (this.controls.select) {
      this.controls.select.disabled = isLoading || this.corpusOptions.length === 0;
    }
    if (!isLoading) {
      this.updateActive();
    }
  }

  setActiveCorpusState({ loadedCorpusId = '', hasActiveArtifacts = false, hasStaleArtifacts = false } = {}) {
    this.loadedCorpusId = loadedCorpusId || '';
    this.hasActiveArtifacts = Boolean(hasActiveArtifacts);
    this.hasStaleArtifacts = Boolean(hasStaleArtifacts);
    this.updateActive();
  }

  renderCorpusOptions() {
    const select = this.controls.select;
    if (!select) return;

    const options = [
      {
        id: '',
        label: this.optionsLoading
          ? this.optionsLoadingLabel
          : (this.corpusOptions.length ? 'Select a saved corpus...' : 'No saved corpora found')
      },
      ...this.corpusOptions.map(option => ({
        id: option.id,
        label: option.label || option.name || option.id
      }))
    ];

    select.innerHTML = options.map(option => {
      const selected = option.id === this.selectedCorpusId ? ' selected' : '';
      return `<option value="${option.id}"${selected}>${option.label}</option>`;
    }).join('');

    select.disabled = this.optionsLoading || this.corpusOptions.length === 0 || this.controls.loadBtn?.dataset.loading === 'true';
    const validSelectedId = this.corpusOptions.some(option => option.id === this.selectedCorpusId)
      ? this.selectedCorpusId
      : (this.corpusOptions[0]?.id || '');
    this.selectedCorpusId = validSelectedId;
    select.value = validSelectedId;
  }

  setCorpusOptionsLoading(isLoading, label = 'Loading saved corpora...') {
    this.optionsLoading = Boolean(isLoading);
    this.optionsLoadingLabel = label || 'Loading saved corpora...';
    this.renderCorpusOptions();
    this.updateActive();
  }

  setCatalogSurfaceAccess({ canUse = false, currentSurface = 'published' } = {}) {
    this.canUseCatalogSurface = Boolean(canUse);
    this.catalogSurface = this.canUseCatalogSurface && currentSurface === 'wip'
      ? 'wip'
      : 'published';
    this.updateActive();
  }
}
