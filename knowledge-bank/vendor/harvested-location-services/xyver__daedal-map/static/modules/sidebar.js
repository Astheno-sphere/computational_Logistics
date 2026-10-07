/**
 * Sidebar - UI components for sidebar resizing.
 * Combines ResizeManager and SidebarResizer.
 */

// ============================================================================
// RESIZE MANAGER - Draggable resize handles for sidebar sections
// ============================================================================

export const ResizeManager = {
  activeHandle: null,
  startY: 0,
  startHeights: {},

  /**
   * Initialize resize manager
   */
  init() {
    this.setupResizeHandle('resizeInput', 'chatMessages', 'chatInputArea', true);
    this.setupResizeHandle('resizeOrder', 'chatInputArea', 'orderPanel', false);
  },

  /**
   * Setup a resize handle
   * @param {string} handleId - ID of the resize handle element
   * @param {string} aboveId - ID of the element above the handle
   * @param {string} belowId - ID of the element below the handle
   * @param {boolean} aboveFlexible - If true, above element uses flex, else fixed height
   */
  setupResizeHandle(handleId, aboveId, belowId, aboveFlexible) {
    const handle = document.getElementById(handleId);
    const above = document.getElementById(aboveId);
    const below = document.getElementById(belowId);

    if (!handle || !above || !below) return;

    handle.addEventListener('mousedown', (e) => {
      e.preventDefault();
      this.activeHandle = { handle, above, below, aboveFlexible };
      this.startY = e.clientY;
      this.startHeights = {
        above: above.offsetHeight,
        below: below.offsetHeight
      };
      handle.classList.add('active');
      document.body.style.cursor = 'ns-resize';
      document.body.style.userSelect = 'none';
    });

    // Touch support
    handle.addEventListener('touchstart', (e) => {
      e.preventDefault();
      const touch = e.touches[0];
      this.activeHandle = { handle, above, below, aboveFlexible };
      this.startY = touch.clientY;
      this.startHeights = {
        above: above.offsetHeight,
        below: below.offsetHeight
      };
      handle.classList.add('active');
    }, { passive: false });

    // Global mouse/touch move and up handlers
    document.addEventListener('mousemove', (e) => this.handleMove(e.clientY));
    document.addEventListener('mouseup', () => this.handleEnd());
    document.addEventListener('touchmove', (e) => {
      if (this.activeHandle) {
        e.preventDefault();
        this.handleMove(e.touches[0].clientY);
      }
    }, { passive: false });
    document.addEventListener('touchend', () => this.handleEnd());
  },

  /**
   * Handle drag movement
   */
  handleMove(clientY) {
    if (!this.activeHandle) return;

    const { above, below, aboveFlexible } = this.activeHandle;
    const deltaY = clientY - this.startY;

    // Calculate new heights
    let newAboveHeight = this.startHeights.above + deltaY;
    let newBelowHeight = this.startHeights.below - deltaY;

    // Get min heights from CSS
    const aboveMinHeight = parseInt(getComputedStyle(above).minHeight) || 60;
    const belowMinHeight = parseInt(getComputedStyle(below).minHeight) || 60;

    // Enforce minimums
    if (newAboveHeight < aboveMinHeight) {
      newAboveHeight = aboveMinHeight;
      newBelowHeight = this.startHeights.above + this.startHeights.below - aboveMinHeight;
    }
    if (newBelowHeight < belowMinHeight) {
      newBelowHeight = belowMinHeight;
      newAboveHeight = this.startHeights.above + this.startHeights.below - belowMinHeight;
    }

    // Apply heights
    if (aboveFlexible) {
      // For chat messages, set flex-basis instead of height
      above.style.flex = `0 0 ${newAboveHeight}px`;
    } else {
      above.style.height = `${newAboveHeight}px`;
    }
    below.style.height = `${newBelowHeight}px`;
  },

  /**
   * Handle drag end
   */
  handleEnd() {
    if (!this.activeHandle) return;

    this.activeHandle.handle.classList.remove('active');
    this.activeHandle = null;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  }
};

// ============================================================================
// SIDEBAR RESIZER - Handles sidebar width resizing
// ============================================================================

export const SidebarResizer = {
  isResizing: false,
  startX: 0,
  startWidth: 0,
  minWidth: 300,
  maxWidth: 800,

  /**
   * Initialize sidebar resizer
   */
  init() {
    const handle = document.getElementById('sidebarResizeHandle');
    const sidebar = document.getElementById('sidebar');

    if (!handle || !sidebar) return;

    // Mouse events
    handle.addEventListener('mousedown', (e) => {
      e.preventDefault();
      this.startResize(e.clientX, sidebar, handle);
    });

    // Touch events
    handle.addEventListener('touchstart', (e) => {
      e.preventDefault();
      const touch = e.touches[0];
      this.startResize(touch.clientX, sidebar, handle);
    }, { passive: false });

    // Global move and end handlers
    document.addEventListener('mousemove', (e) => this.handleMove(e.clientX));
    document.addEventListener('mouseup', () => this.handleEnd());
    document.addEventListener('touchmove', (e) => {
      if (this.isResizing) {
        e.preventDefault();
        this.handleMove(e.touches[0].clientX);
      }
    }, { passive: false });
    document.addEventListener('touchend', () => this.handleEnd());

    // Store sidebar reference
    this.sidebar = sidebar;
    this.handle = handle;
  },

  /**
   * Start resizing
   */
  startResize(clientX, sidebar, handle) {
    this.isResizing = true;
    this.startX = clientX;
    this.startWidth = sidebar.offsetWidth;
    handle.classList.add('active');
    document.body.style.cursor = 'ew-resize';
    document.body.style.userSelect = 'none';
  },

  /**
   * Handle drag movement
   */
  handleMove(clientX) {
    if (!this.isResizing) return;

    const deltaX = clientX - this.startX;
    let newWidth = this.startWidth + deltaX;

    // Enforce min/max
    newWidth = Math.max(this.minWidth, Math.min(this.maxWidth, newWidth));

    // Apply new width
    this.sidebar.style.width = newWidth + 'px';
  },

  /**
   * Handle drag end
   */
  handleEnd() {
    if (!this.isResizing) return;

    this.isResizing = false;
    this.handle.classList.remove('active');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  }
};
