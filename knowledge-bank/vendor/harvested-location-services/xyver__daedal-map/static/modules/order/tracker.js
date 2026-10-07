/**
 * Order Tracker
 * Polls backend for order queue status updates.
 * Uses callbacks for completion/failure - no app-specific dependencies.
 */

import { checkOrderStatus, cancelOrder } from '../chat/api.js';

export class OrderTracker {
  /**
   * @param {Object} config
   * @param {HTMLElement} config.container - DOM element for status indicators
   * @param {Function} config.onReady - Called when order completes: (queueId, result) => void
   * @param {Function} config.onFailed - Called when order fails: (queueId, error) => void
   * @param {number} [config.pollIntervalMs=500] - Polling interval in ms
   */
  constructor(config) {
    this.container = config.container;
    this.onReady = config.onReady || (() => {});
    this.onFailed = config.onFailed || (() => {});
    this.pollIntervalMs = config.pollIntervalMs || 500;
    this.getSessionId = config.getSessionId || (() => null);

    this.pendingOrders = new Map();  // queue_id -> order info
    this.pollInterval = null;
  }

  /**
   * Add an order to tracking and start polling.
   * @param {string} queueId - Queue ID from backend
   * @param {Object} orderInfo - Order metadata { items, summary }
   */
  addOrder(queueId, orderInfo) {
    this.pendingOrders.set(queueId, {
      ...orderInfo,
      status: 'pending',
      progress: 0,
      addedAt: Date.now()
    });
    this.startPolling();
    this.renderStatus(queueId);
  }

  /**
   * Start polling for order status updates.
   */
  startPolling() {
    if (this.pollInterval) return;  // Already polling

    this.pollInterval = setInterval(() => this.checkOrders(), this.pollIntervalMs);
    console.log('[OrderTracker] Started polling');
  }

  /**
   * Stop polling when no orders are pending.
   */
  stopPolling() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
      console.log('[OrderTracker] Stopped polling');
    }
  }

  /**
   * Check status of all pending orders.
   */
  async checkOrders() {
    if (this.pendingOrders.size === 0) {
      this.stopPolling();
      return;
    }

    const queueIds = Array.from(this.pendingOrders.keys());
    const sessionId = this.getSessionId();

    try {
      const statuses = await checkOrderStatus(queueIds, sessionId);

      for (const [queueId, status] of Object.entries(statuses)) {
        const order = this.pendingOrders.get(queueId);
        if (!order) continue;

        // Update local state
        order.status = status.status;
        order.progress = status.progress || 0;
        order.message = status.message;

        // Update UI
        this.renderStatus(queueId);

        // Handle completion
        if (status.status === 'complete') {
          this.handleReady(queueId, status.result);
        } else if (status.status === 'failed') {
          this.handleFailed(queueId, status.error);
        } else if (status.status === 'cancelled') {
          this.pendingOrders.delete(queueId);
          this.removeStatusElement(queueId);
        }
      }
    } catch (error) {
      console.error('[OrderTracker] Poll error:', error);
    }
  }

  /**
   * Handle completed order.
   * @param {string} queueId - Queue ID
   * @param {Object} result - Result data from backend
   */
  handleReady(queueId, result) {
    console.log('[OrderTracker] Order ready:', queueId);
    this.removeStatusElement(queueId);
    this.pendingOrders.delete(queueId);
    this.onReady(queueId, result);
  }

  /**
   * Handle failed order.
   * @param {string} queueId - Queue ID
   * @param {string} error - Error message
   */
  handleFailed(queueId, error) {
    console.error('[OrderTracker] Order failed:', queueId, error);
    // Show failure briefly before removing
    setTimeout(() => {
      this.removeStatusElement(queueId);
    }, 3000);
    this.pendingOrders.delete(queueId);
    this.onFailed(queueId, error);
  }

  /**
   * Cancel a pending order.
   * @param {string} queueId - Queue ID to cancel
   */
  async cancel(queueId) {
    try {
      await cancelOrder(queueId, this.getSessionId());
      this.pendingOrders.delete(queueId);
      this.removeStatusElement(queueId);
    } catch (error) {
      console.error('[OrderTracker] Cancel error:', error);
    }
  }

  /**
   * Render status indicator for an order.
   * @param {string} queueId - Queue ID to render
   */
  renderStatus(queueId) {
    const order = this.pendingOrders.get(queueId);
    if (!order || !this.container) return;

    // Find or create status element
    let statusEl = document.getElementById(`queue-status-${queueId}`);
    if (!statusEl) {
      statusEl = document.createElement('div');
      statusEl.id = `queue-status-${queueId}`;
      statusEl.className = 'order-queue-status';
      this.container.insertBefore(statusEl, this.container.firstChild);
    }

    const progressPercent = Math.round(order.progress * 100);
    const statusMessages = {
      'pending': 'Queued',
      'executing': 'Processing...',
      'complete': 'Ready!',
      'failed': 'Failed'
    };

    statusEl.innerHTML = `
      <div class="queue-status-header">
        <span class="queue-status-label">${statusMessages[order.status] || order.status}</span>
        <span class="queue-status-progress">${progressPercent}%</span>
      </div>
      <div class="queue-progress-bar">
        <div class="queue-progress-fill" style="width: ${progressPercent}%"></div>
      </div>
      ${order.message ? `<div class="queue-status-message">${order.message}</div>` : ''}
    `;

    statusEl.className = `order-queue-status status-${order.status}`;
  }

  /**
   * Remove a status element from the DOM.
   * @param {string} queueId - Queue ID
   */
  removeStatusElement(queueId) {
    const statusEl = document.getElementById(`queue-status-${queueId}`);
    if (statusEl) statusEl.remove();
  }

  /**
   * Get queue statistics.
   * @returns {Object} { pending, isPolling }
   */
  getStats() {
    return {
      pending: this.pendingOrders.size,
      isPolling: this.pollInterval !== null
    };
  }
}
