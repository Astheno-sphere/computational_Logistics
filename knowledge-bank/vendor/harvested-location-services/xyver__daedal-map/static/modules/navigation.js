/**
 * Navigation Manager - Hierarchical navigation state and breadcrumbs.
 * Handles navigation path tracking and breadcrumb UI.
 */

import { CONFIG } from './config.js';

// Dependencies set via setDependencies to avoid circular imports
let MapAdapter = null;
let ViewportLoader = null;
let App = null;

export function setDependencies(deps) {
  MapAdapter = deps.MapAdapter;
  ViewportLoader = deps.ViewportLoader;
  App = deps.App;
}

// ============================================================================
// NAVIGATION MANAGER - Hierarchical navigation state
// ============================================================================

export const NavigationManager = {
  path: [],  // Array of {loc_id, name, level}
  currentLevel: 'world',
  isNavigating: false,  // Flag to prevent duplicate navigation

  /**
   * Reset navigation to world view
   */
  reset() {
    this.path = [{ loc_id: 'world', name: 'World', level: 'world' }];
    this.currentLevel = 'world';
    this.isNavigating = false;
    this.updateBreadcrumb();
  },

  /**
   * Push a new location onto the navigation path
   * @param {string} locId - Location ID
   * @param {string} name - Display name
   * @param {string} level - Geographic level
   */
  push(locId, name, level) {
    // Prevent duplicate entries - check if last entry has same loc_id
    const lastEntry = this.path[this.path.length - 1];
    if (lastEntry && lastEntry.loc_id === locId) {
      console.log(`Skipping duplicate navigation entry: ${locId}`);
      return;
    }
    this.path.push({ loc_id: locId, name: name, level: level });
    this.currentLevel = level;
    this.updateBreadcrumb();
  },

  /**
   * Navigate up to a specific index in the path
   * @param {number} index - Target index
   */
  async navigateTo(index) {
    if (index < 0 || index >= this.path.length - 1) return;

    // Prevent duplicate navigation
    if (this.isNavigating) {
      console.log('Navigation already in progress, skipping');
      return;
    }
    this.isNavigating = true;

    const target = this.path[index];
    this.path = this.path.slice(0, index + 1);
    this.currentLevel = target.level;
    this.updateBreadcrumb();

    // Clear all overlays when navigating back (memory cleanup)
    MapAdapter?.clearParentOutline();
    MapAdapter?.clearCityOverlay();

    try {
      if (target.loc_id === 'world') {
        await App?.loadCountries();
      } else {
        // Navigate to target's children (no parent outline when going back)
        await App?.drillDown(target.loc_id, target.name, true);
      }
    } finally {
      this.isNavigating = false;
    }
  },

  /**
   * Update breadcrumb UI
   */
  updateBreadcrumb() {
    const container = document.getElementById('breadcrumb');
    if (!container) return;

    const crumbs = this.path.map((item, index) => {
      const isLast = index === this.path.length - 1;
      if (isLast) {
        return `<span class="current">${item.name}</span>`;
      } else {
        // Clicking breadcrumb zooms to that level, keeping viewport centered
        return `<span onclick="NavigationManager.zoomToLevel(${index})">${item.name}</span>`;
      }
    });

    container.innerHTML = crumbs.join(' &gt; ');
  },

  /**
   * Update breadcrumb to show current admin level (for viewport-based navigation)
   * @param {number} adminLevel - Current admin level
   */
  updateLevelDisplay(adminLevel) {
    const levelNames = ['World', 'States', 'Counties', 'Tracts', 'Block Groups', 'Blocks'];

    if (ViewportLoader?.enabled) {
      this.path = [];
      for (let i = 0; i <= adminLevel; i++) {
        const name = levelNames[i] || `Level ${i}`;
        this.path.push({
          loc_id: i === 0 ? 'world' : `level_${i}`,
          name: name,
          level: i === 0 ? 'world' : `level_${i}`
        });
      }
      this.updateBreadcrumb();
    }
  },

  /**
   * Zoom to a specific breadcrumb level (keeps viewport centered)
   * @param {number} index - Index in the path
   */
  zoomToLevel(index) {
    if (index < 0 || index >= this.path.length) return;

    const target = this.path[index];

    // If using viewport-based navigation, just zoom to the target level
    if (ViewportLoader?.enabled) {
      const adminLevel = index;  // World=0, States=1, etc.
      const targetZoom = ViewportLoader.getZoomForAdminLevel(adminLevel);
      const center = MapAdapter?.map.getCenter();

      MapAdapter?.map.flyTo({ center, zoom: targetZoom });
      return;
    }

    // Fall back to legacy drill-down navigation
    this.navigateTo(index);
  },

  /**
   * Get zoom level based on current navigation depth
   * @returns {number} Recommended zoom level
   */
  getZoomForLevel() {
    switch (this.currentLevel) {
      case 'world': return 2;
      case 'country': return 4;
      case 'us_state': return 6;
      case 'state': return 6;
      case 'us_county': return 8;
      case 'county': return 8;
      case 'city': return 10;
      default: return 4;
    }
  },

  /**
   * Zoom to a specific admin level (for level buttons)
   * @param {number} adminLevel - Target admin level (0=world, 1=states, 2=counties, 3=local)
   */
  zoomToAdminLevel(adminLevel) {
    if (!MapAdapter?.map) return;

    // Get target zoom calculated from viewport area thresholds
    const targetArea = ViewportLoader?.getTargetAreaForAdminLevel(adminLevel);
    const targetZoom = ViewportLoader?.getZoomForAdminLevel(adminLevel) || [2, 5, 8, 11][adminLevel];
    const center = MapAdapter.map.getCenter();

    console.log(`Zooming to admin level ${adminLevel} (target area: ${targetArea} sq deg, zoom: ${targetZoom.toFixed(1)})`);
    MapAdapter.map.flyTo({ center, zoom: targetZoom, duration: 1000 });

    // If locked, update the locked level to match the clicked button
    if (ViewportLoader?.levelLocked) {
      ViewportLoader.lockedLevel = adminLevel;
      ViewportLoader.currentAdminLevel = adminLevel;
      console.log(`Lock updated to level ${adminLevel}`);
    }

    // Update active button
    this.updateLevelButtons(adminLevel);
  },

  /**
   * Update level button active states
   * @param {number} activeLevel - Currently active admin level
   */
  updateLevelButtons(activeLevel) {
    const container = document.getElementById('levelButtons');
    if (!container) return;

    const buttons = container.querySelectorAll('button');
    buttons.forEach(btn => {
      const level = parseInt(btn.dataset.level);
      btn.classList.toggle('active', level === activeLevel);
    });
  },

  /**
   * Initialize level button click handlers
   */
  initLevelButtons() {
    const container = document.getElementById('levelButtons');
    if (!container) return;

    container.addEventListener('click', (e) => {
      if (e.target.tagName === 'BUTTON' && e.target.dataset.level !== undefined) {
        const level = parseInt(e.target.dataset.level);
        this.zoomToAdminLevel(level);
      }
    });

    // Initialize lock button
    const lockBtn = document.getElementById('levelLockBtn');
    if (lockBtn) {
      lockBtn.addEventListener('click', () => this.toggleLevelLock());
    }

    // Update active button on zoom changes
    if (MapAdapter?.map) {
      MapAdapter.map.on('zoomend', () => {
        const bounds = MapAdapter.map.getBounds();
        const currentLevel = ViewportLoader?.getAdminLevelForViewport(bounds) || 0;
        // Only update buttons if not locked
        if (!ViewportLoader?.levelLocked) {
          this.updateLevelButtons(currentLevel);
        }
      });
    }
  },

  /**
   * Toggle the admin level lock
   */
  toggleLevelLock() {
    const isLocked = ViewportLoader?.toggleLock();
    this.updateLockButton(isLocked);

    // When locking, also update the level buttons to show locked level
    if (isLocked) {
      this.updateLevelButtons(ViewportLoader.lockedLevel);
    }
  },

  /**
   * Update lock button appearance
   * @param {boolean} isLocked - Current lock state
   */
  updateLockButton(isLocked) {
    const lockBtn = document.getElementById('levelLockBtn');
    if (!lockBtn) return;

    lockBtn.classList.toggle('locked', isLocked);
    lockBtn.title = isLocked ? 'Unlock admin level (currently locked)' : 'Lock admin level';
  }
};

// Make navigateTo available globally for onclick handlers
if (typeof window !== 'undefined') {
  window.NavigationManager = NavigationManager;
}
