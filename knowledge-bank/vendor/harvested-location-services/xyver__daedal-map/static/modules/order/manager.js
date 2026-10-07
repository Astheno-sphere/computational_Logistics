/**
 * Order Panel Manager
 * Handles order panel rendering with Order/Loaded tabs.
 * Order tab shows pending items, Loaded tab shows cached data per source.
 *
 * Usage:
 *   const panel = new OrderPanel({
 *     elements: { panel, orderTab, loadedTab, orderContent, loadedContent, ... },
 *     onConfirm: async (order) => { ... },
 *     onClear: () => { ... },
 *     onClearSource: (overlayId) => { ... },
 *     getCacheStats: () => ({ overlays, totals }),
 *     addMessage: (text, type) => { ... }
 *   });
 */

export class OrderPanel {
  /**
   * @param {Object} config
   * @param {Object} config.elements - DOM element references
   * @param {Function} config.onConfirm - async (order) => void - Handle order confirmation
   * @param {Function} config.onQueue - async (order) => void - Handle order queueing
   * @param {Function} [config.onClear] - () => void - Handle order clear/reset
   * @param {Function} [config.onClearSource] - (overlayId) => void - Clear a single source
   * @param {Function} [config.getCacheStats] - () => { overlays, totals }
   * @param {Function} [config.addMessage] - (text, type) => void - Display chat message
   */
  constructor(config) {
    this.elements = config.elements || {};
    this.onConfirm = config.onConfirm || (() => {});
    this.onQueue = config.onQueue || (() => {});
    this.onClear = config.onClear || (() => {});
    this.onClearSource = config.onClearSource || (() => {});
    this.getCacheStats = config.getCacheStats || (() => null);
    this.addMessage = config.addMessage || (() => {});

    this.currentOrder = null;
    this.activeTab = 'order';
  }

  /**
   * Initialize the order panel - setup listeners and initial render.
   */
  init() {
    this.setupEventListeners();
    this.render();
    this.renderLoadedTab();

    // Listen for cache updates
    window.addEventListener('overlayCacheUpdated', () => {
      this.renderLoadedTab();
    });
  }

  /**
   * Setup event listeners for panel buttons and tabs.
   */
  setupEventListeners() {
    const { confirmBtn, cancelBtn, orderTabBtn, loadedTabBtn, loadedClearAllBtn } = this.elements;

    if (confirmBtn) {
      confirmBtn.addEventListener('click', () => this.confirmOrder());
    }

    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => this.clearOrder());
    }

    if (orderTabBtn) {
      orderTabBtn.addEventListener('click', () => this.switchTab('order'));
    }

    if (loadedTabBtn) {
      loadedTabBtn.addEventListener('click', () => this.switchTab('loaded'));
    }

    if (loadedClearAllBtn) {
      loadedClearAllBtn.addEventListener('click', () => this.clearAllLoaded());
    }
  }

  /**
   * Switch between Order and Loaded tabs.
   * @param {string} tab - 'order' or 'loaded'
   */
  switchTab(tab) {
    this.activeTab = tab;
    const { orderTabBtn, loadedTabBtn, orderTabContent, loadedTabContent } = this.elements;

    if (tab === 'order') {
      if (orderTabBtn) orderTabBtn.classList.add('active');
      if (loadedTabBtn) loadedTabBtn.classList.remove('active');
      if (orderTabContent) orderTabContent.classList.add('active');
      if (loadedTabContent) loadedTabContent.classList.remove('active');
    } else {
      if (orderTabBtn) orderTabBtn.classList.remove('active');
      if (loadedTabBtn) loadedTabBtn.classList.add('active');
      if (orderTabContent) orderTabContent.classList.remove('active');
      if (loadedTabContent) loadedTabContent.classList.add('active');
      this.renderLoadedTab();
    }
  }

  /**
   * Add items from a response to the current order (accumulates until Clear).
   * @param {Object} order - The order object { items, summary, ... }
   * @param {string} summary - Summary text
   */
  setOrder(order, summary, executionOrder = null) {
    if (!order || !order.items || order.items.length === 0) {
      return;
    }

    const orderForExecution = executionOrder || order;
    const orderForDisplay = { ...order, executionOrder: orderForExecution };

    if (!this.currentOrder || !this.currentOrder.items || this.currentOrder.items.length === 0) {
      this.currentOrder = orderForDisplay;
      delete this.currentOrder.navigationLocations;
    } else {
      // Append new items, deduplicate by source_id + metric + region
      const existingKeys = new Set(
        this.currentOrder.items.map(item =>
          `${item.source_id || item.source}|${item.metric}|${item.region}`
        )
      );

      const newItems = orderForDisplay.items.filter(item => {
        const key = `${item.source_id || item.source}|${item.metric}|${item.region}`;
        return !existingKeys.has(key);
      });

      if (newItems.length > 0) {
        this.currentOrder.items = this.currentOrder.items.concat(newItems);
        this.currentOrder.summary = summary || this.currentOrder.summary;
      }
      this.currentOrder.executionOrder = orderForExecution;
      delete this.currentOrder.navigationLocations;
    }

    // Reset confirm button text
    if (this.elements.confirmBtn) {
      this.elements.confirmBtn.textContent = 'Display on Map';
      this.elements.confirmBtn.classList.remove('loading');
    }

    // Switch to order tab when new order arrives
    this.switchTab('order');
    this.render(summary);
  }

  /**
   * Set navigation locations - locations selected, ready for data request.
   * @param {Array} locations - Location objects from navigation
   */
  setNavigationLocations(locations) {
    if (!locations || locations.length === 0) return;

    this.currentOrder = {
      items: [],
      navigationLocations: locations,
      summary: `${locations.length} location${locations.length > 1 ? 's' : ''} selected`
    };

    this.switchTab('order');
    this.renderNavigationMode();
  }

  /**
   * Render order panel in navigation mode (locations selected, awaiting data).
   */
  renderNavigationMode() {
    const { count, items, confirmBtn, summary: summaryEl } = this.elements;

    if (!this.currentOrder || !this.currentOrder.navigationLocations) {
      return this.render();
    }

    const locations = this.currentOrder.navigationLocations;
    if (count) count.textContent = `(${locations.length} location${locations.length > 1 ? 's' : ''})`;
    if (summaryEl) summaryEl.textContent = 'Locations ready - ask for data';
    if (confirmBtn) {
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Add Data First';
    }

    if (items) {
      items.innerHTML = locations.map(loc => {
        const name = loc.matched_term || loc.loc_id || 'Unknown';
        const country = loc.country_name || loc.iso3 || '';
        return `
          <div class="order-item order-item-location">
            <div class="order-item-info">
              <div class="order-item-name">${escapeHtml(name)}</div>
              <div class="order-item-details">${escapeHtml(country)}</div>
            </div>
          </div>
        `;
      }).join('');
    }
  }

  /**
   * Clear the current order and notify consumer.
   */
  clearOrder() {
    this.currentOrder = null;
    this.render();
    this.onClear();
  }

  /**
   * Remove a specific item from the order.
   * @param {number} index - Index of item to remove
   */
  removeItem(index) {
    if (!this.currentOrder || !this.currentOrder.items) return;

    this.currentOrder.items.splice(index, 1);

    if (this.currentOrder.items.length === 0) {
      this.currentOrder = null;
    }

    this.render();
  }

  /**
   * Estimate order data size based on region.
   * @param {Array} items - Order items
   * @returns {Object} { locations, estimatedKB }
   */
  estimateOrderSize(items) {
    const regionCounts = {
      'USA': 3200,
      'USA-CA': 58, 'USA-TX': 254, 'USA-FL': 67, 'USA-NY': 62, 'USA-PA': 67,
      'global': 5000,
      'default': 100
    };

    let totalLocations = 0;
    for (const item of items) {
      const region = item.region || 'global';
      let count = regionCounts[region];
      if (!count) {
        if (region.match(/^USA-[A-Z]{2}$/)) {
          count = regionCounts['default'];
        } else if (region.startsWith('USA')) {
          count = regionCounts['USA'];
        } else {
          count = regionCounts['default'];
        }
      }
      totalLocations += count;
    }

    return { locations: totalLocations, estimatedKB: totalLocations };
  }

  /**
   * Render the order tab content.
   * @param {string} [summary] - Optional summary text
   */
  render(summary = '') {
    const { count, items, confirmBtn, summary: summaryEl } = this.elements;

    if (summaryEl) summaryEl.textContent = summary || '';

    // Empty state
    if (!this.currentOrder || !this.currentOrder.items || this.currentOrder.items.length === 0) {
      if (count) count.textContent = '(empty)';
      if (items) items.innerHTML = '<div style="color: #999; font-size: 12px; text-align: center; padding: 10px;">Ask for data to add items here</div>';
      if (confirmBtn) {
        confirmBtn.disabled = true;
        confirmBtn.textContent = 'Display on Map';
      }
      return;
    }

    // Render items with size estimate
    const orderItems = this.currentOrder.items;
    const sizeEstimate = this.estimateOrderSize(orderItems);
    const sizeStr = sizeEstimate.estimatedKB >= 1024
      ? `~${(sizeEstimate.estimatedKB / 1024).toFixed(1)} MB`
      : `~${sizeEstimate.estimatedKB} KB`;

    if (count) count.textContent = `(${orderItems.length} item${orderItems.length > 1 ? 's' : ''}, ${sizeStr})`;
    if (confirmBtn) confirmBtn.disabled = false;

    // Check for invalid items
    const hasInvalid = orderItems.some(item => item._valid === false);
    if (confirmBtn) {
      confirmBtn.disabled = hasInvalid;
      confirmBtn.title = hasInvalid ? 'Fix invalid items before displaying' : '';
    }

    // Check if this is a removal order (order-level or all items are removes)
    const orderAction = this.currentOrder.action || 'add';
    const hasRemoves = orderItems.some(item => (item.action || orderAction) === 'remove');
    const hasAdds = orderItems.some(item => (item.action || orderAction) === 'add');
    const isMixedOrder = hasRemoves && hasAdds;
    const isAllRemoves = hasRemoves && !hasAdds;

    // Update button text based on order type
    if (confirmBtn) {
      if (isAllRemoves) {
        confirmBtn.textContent = 'Remove from Map';
      } else if (isMixedOrder) {
        confirmBtn.textContent = 'Update Map';
      } else {
        confirmBtn.textContent = 'Display on Map';
      }
    }

    if (items) {
      items.innerHTML = orderItems.map((item, index) => {
        // For geometry items, derive label from source_id; for data items, use metric_label/metric
        const geometryLabel = item.overlay_type ? (item.source_id || '').replace('geometry_', '').toUpperCase() : null;
        const label = geometryLabel || item.metric_label || item.metric || 'unknown';
        const region = item.region || 'global';
        let year;
        if (item.year_start && item.year_end) {
          year = `${item.year_start}-${item.year_end}`;
        } else {
          year = item.year || 'latest';
        }
        const isValid = item._valid !== false;
        const error = item._error || '';
        const details = [region, year].filter(Boolean).join(' | ');

        // Check item-level action, fall back to order-level action
        const itemAction = item.action || orderAction;
        const isRemoval = itemAction === 'remove';

        const itemClass = isValid
          ? (isRemoval ? 'order-item order-item-removal' : 'order-item')
          : 'order-item order-item-invalid';
        const errorHtml = error ? `<div class="order-item-error">${escapeHtml(error)}</div>` : '';
        const actionBadge = isRemoval
          ? '<span class="order-action-badge remove">REMOVE</span>'
          : (isMixedOrder ? '<span class="order-action-badge add">ADD</span>' : '');

        return `
          <div class="${itemClass}">
            <div class="order-item-info">
              <div class="order-item-name">${actionBadge}${escapeHtml(label)}</div>
              <div class="order-item-details">${escapeHtml(details)}</div>
              ${errorHtml}
            </div>
            <button class="order-item-remove" data-remove-index="${index}" title="Remove">x</button>
          </div>
        `;
      }).join('');

      // Bind remove buttons
      items.querySelectorAll('.order-item-remove').forEach(btn => {
        btn.addEventListener('click', () => {
          this.removeItem(parseInt(btn.dataset.removeIndex, 10));
        });
      });
    }
  }

  /**
   * Render the Loaded tab content from cache stats.
   */
  renderLoadedTab() {
    const { loadedItems, loadedActions } = this.elements;
    if (!loadedItems) return;

    const stats = this.getCacheStats();
    if (!stats || !stats.overlays || Object.keys(stats.overlays).length === 0) {
      loadedItems.innerHTML = '<div style="color: #999; font-size: 12px; text-align: center; padding: 10px;">No data loaded</div>';
      if (loadedActions) loadedActions.style.display = 'none';
      return;
    }

    let html = '';
    for (const [overlayId, info] of Object.entries(stats.overlays)) {
      const name = formatOverlayName(overlayId);
      const featureStr = `${info.features.toLocaleString()} event${info.features !== 1 ? 's' : ''}`;

      // Format time range
      let rangeStr = '';
      if (info.rangeStart && info.rangeEnd) {
        rangeStr = formatDateRange(info.rangeStart, info.rangeEnd);
      } else if (info.yearRange && info.yearRange !== 'none') {
        rangeStr = info.yearRange;
      }

      const sizeStr = parseFloat(info.sizeMB) >= 1
        ? `${parseFloat(info.sizeMB).toFixed(1)} MB`
        : `${Math.round(parseFloat(info.sizeMB) * 1024)} KB`;

      const details = [featureStr, rangeStr, sizeStr].filter(Boolean).join(' - ');

      html += `
        <div class="loaded-item" data-overlay-id="${overlayId}">
          <div class="loaded-item-info">
            <div class="loaded-item-name">${escapeHtml(name)}</div>
            <div class="loaded-item-details">${escapeHtml(details)}</div>
          </div>
          <button class="loaded-item-clear" data-clear-overlay="${overlayId}" title="Clear ${name}">Clear</button>
        </div>
      `;
    }

    // Totals
    const totalFeatures = stats.totals.features || 0;
    const totalMB = parseFloat(stats.totals.sizeMB || 0);
    const totalStr = totalMB >= 1
      ? `${totalMB.toFixed(1)} MB`
      : `${Math.round(totalMB * 1024)} KB`;
    html += `<div class="loaded-totals">${totalFeatures.toLocaleString()} features total (${totalStr})</div>`;

    loadedItems.innerHTML = html;
    if (loadedActions) loadedActions.style.display = 'flex';

    // Bind clear buttons
    loadedItems.querySelectorAll('.loaded-item-clear').forEach(btn => {
      btn.addEventListener('click', () => {
        const overlayId = btn.dataset.clearOverlay;
        this.clearSource(overlayId);
      });
    });
  }

  /**
   * Clear a single source from loaded data.
   * @param {string} overlayId - The overlay to clear
   */
  clearSource(overlayId) {
    this.onClearSource(overlayId);
    this.renderLoadedTab();
  }

  /**
   * Clear all loaded data.
   */
  clearAllLoaded() {
    const stats = this.getCacheStats();
    if (!stats || !stats.overlays) return;

    for (const overlayId of Object.keys(stats.overlays)) {
      this.onClearSource(overlayId);
    }
    this.renderLoadedTab();
  }

  /**
   * Confirm the current order via callback.
   */
  async confirmOrder() {
    if (!this.currentOrder) return;

    const { confirmBtn } = this.elements;
    if (confirmBtn) {
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Sending...';
      confirmBtn.classList.add('loading');
    }

    try {
      await this.onConfirm(this.currentOrder.executionOrder || this.currentOrder);
      // On success: clear order, switch to loaded tab
      this.currentOrder = null;
      this.render();
      this.renderLoadedTab();
      this.switchTab('loaded');
    } catch (error) {
      console.error('[OrderPanel] Confirm error:', error);
      this.addMessage('Sorry, something went wrong executing the order.', 'assistant');
    } finally {
      if (confirmBtn) {
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Display on Map';
        confirmBtn.classList.remove('loading');
      }
    }
  }

  /**
   * Queue order for background processing via callback.
   */
  async queueOrder() {
    if (!this.currentOrder) return;

    const { confirmBtn } = this.elements;
    if (confirmBtn) {
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Queueing...';
      confirmBtn.classList.add('loading');
    }

    try {
      await this.onQueue(this.currentOrder);
      if (confirmBtn) {
        confirmBtn.textContent = 'Queued';
        confirmBtn.classList.remove('loading');
      }
    } catch (error) {
      console.error('[OrderPanel] Queue error:', error);
      this.addMessage('Failed to queue order. Try again.', 'assistant');
      if (confirmBtn) {
        confirmBtn.textContent = 'Display on Map';
        confirmBtn.classList.remove('loading');
      }
    } finally {
      if (confirmBtn) confirmBtn.disabled = false;
    }
  }
}

/**
 * Format overlay ID to display name.
 * @param {string} overlayId
 * @returns {string}
 */
function formatOverlayName(overlayId) {
  const names = {
    earthquakes: 'Earthquakes',
    volcanoes: 'Volcanoes',
    tsunamis: 'Tsunamis',
    hurricanes: 'Hurricanes',
    hurricanes_live: 'Hurricanes',
    wildfires: 'Wildfires',
    tornadoes: 'Tornadoes',
    floods: 'Floods',
    drought: 'Drought',
    landslides: 'Landslides',
    temperature: 'Temperature',
    precipitation: 'Precipitation',
    wind: 'Wind',
    humidity: 'Humidity'
  };
  return names[overlayId] || overlayId.charAt(0).toUpperCase() + overlayId.slice(1);
}

/**
 * Format a timestamp range as a readable date range string.
 * @param {number} startMs - Start timestamp in ms
 * @param {number} endMs - End timestamp in ms
 * @returns {string}
 */
function formatDateRange(startMs, endMs) {
  const start = new Date(startMs);
  const end = new Date(endMs);
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  const startYear = start.getFullYear();
  const endYear = end.getFullYear();

  if (startYear === endYear) {
    return `${months[start.getMonth()]} - ${months[end.getMonth()]} ${endYear}`;
  }
  return `${months[start.getMonth()]} ${startYear} - ${months[end.getMonth()]} ${endYear}`;
}

/**
 * Escape HTML to prevent XSS.
 * @param {string} text - Raw text
 * @returns {string} Escaped HTML
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
