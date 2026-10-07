/**
 * ChatCore - Reusable chat orchestrator
 *
 * Ties together session, API, and message rendering.
 * Consumers provide response handlers via callbacks (map vs admin).
 *
 * Usage:
 *   const chat = new ChatCore({
 *     messagesContainer: document.getElementById('chatMessages'),
 *     historyLimit: 10,
 *     getContext: () => ({ viewport, overlays, ... }),  // app-specific context
 *     onResponse: (response) => { ... },               // app-specific handler
 *     onError: (error) => { ... }                      // optional error handler
 *   });
 */

import {
  getOrCreateSessionId,
  resetSessionId,
  saveChatState,
  clearChatStorage
} from './session.js';

import {
  addMessage,
  showTypingIndicator,
  escapeHtml,
  formatMessage
} from './message-renderer.js';

import {
  sendStreamingRequest,
  sendChatRequest,
  clearBackendSession
} from './api.js';

export class ChatCore {
  /**
   * @param {Object} config
   * @param {HTMLElement} config.messagesContainer - Chat messages DOM container
   * @param {number} [config.historyLimit=10] - Max history entries to send to API
   * @param {Function} [config.getContext] - Returns app-specific context for API payload
   * @param {Function} [config.onResponse] - Handler for API responses
   * @param {Function} [config.onError] - Handler for errors
   * @param {boolean} [config.streaming=true] - Use streaming endpoint
   */
  constructor(config) {
    this.container = config.messagesContainer;
    this.historyLimit = config.historyLimit || 10;
    this.getContext = config.getContext || (() => ({}));
    this.onResponse = config.onResponse || (() => {});
    this.onError = config.onError || ((err) => console.error('ChatCore error:', err));
    this.streaming = config.streaming !== false;

    this.history = [];
    this.sessionId = getOrCreateSessionId();
  }

  /**
   * Send a message and handle the response cycle.
   * Adds user message, shows indicator, calls API, delegates to onResponse.
   * @param {string} text - User message text
   * @returns {Promise<Object|null>} API response or null on error
   */
  async sendMessage(text) {
    if (!text.trim()) return null;

    // Add user message to UI and history
    this.addMessage(text, 'user');
    this.history.push({ role: 'user', content: text });

    // Show loading indicator
    const indicator = this.showTypingIndicator(this.streaming);

    try {
      // Build payload with app-specific context
      const context = this.getContext();
      const payload = {
        query: text,
        chatHistory: this.history.slice(-this.historyLimit),
        sessionId: this.sessionId,
        ...context
      };

      // Send request (streaming or simple)
      let response;
      if (this.streaming) {
        response = await sendStreamingRequest(payload, (stage, message) => {
          indicator.updateStage(stage, message);
        });
      } else {
        response = await sendChatRequest(payload);
      }

      if (!response) {
        throw new Error('No response received from server');
      }

      // Track in history
      this.history.push({ role: 'assistant', content: response.message || response.summary });

      // Delegate to consumer's response handler
      this.onResponse(response);

      return response;
    } catch (error) {
      this.onError(error);
      if (error?.data?.type === 'error') {
        this.addMessage(error.data.message || 'Request blocked.', 'assistant');
      } else {
        this.addMessage('Sorry, something went wrong. Please try again.', 'assistant');
      }
      return null;
    } finally {
      indicator.remove();
    }
  }

  /**
   * Send a message with a resolved location (after disambiguation).
   * @param {string} text - Original query
   * @param {Object} resolvedLocation - { loc_id, iso3, matched_term, country_name }
   * @returns {Promise<Object|null>} API response
   */
  async sendWithLocation(text, resolvedLocation) {
    this.history.push({ role: 'user', content: text });

    const context = this.getContext();
    const payload = {
      query: text,
      chatHistory: this.history.slice(-this.historyLimit),
      sessionId: this.sessionId,
      resolved_location: resolvedLocation,
      ...context
    };

    const response = await sendChatRequest(payload);
    if (response) {
      this.history.push({ role: 'assistant', content: response.message || response.summary });
    }
    return response;
  }

  /**
   * Add a message to the chat UI.
   * @param {string} text - Message text
   * @param {string} type - 'user' or 'assistant'
   * @param {Object} [options] - { html: boolean }
   * @returns {HTMLElement} The message element
   */
  addMessage(text, type, options = {}) {
    const div = addMessage(this.container, text, type, options);
    this.saveChatState();
    return div;
  }

  /**
   * Show typing/loading indicator.
   * @param {boolean} [staged=false] - Show staged progress indicator
   * @returns {HTMLElement} Indicator with updateStage method
   */
  showTypingIndicator(staged = false) {
    return showTypingIndicator(this.container, staged);
  }

  /**
   * Clear session - reset to fresh state.
   * Clears history, UI, localStorage, and backend session.
   * @returns {string} New session ID
   */
  async clearSession() {
    const oldSessionId = this.sessionId;

    // Clear state
    this.history = [];
    if (this.container) {
      this.container.innerHTML = '';
    }

    // Reset session
    this.sessionId = resetSessionId();
    clearChatStorage();

    // Notify backend
    if (oldSessionId) {
      await clearBackendSession(oldSessionId);
    }

    console.log('[ChatCore] Session cleared, new session:', this.sessionId);
    return this.sessionId;
  }

  /**
   * Persist explicit chat state if enabled.
   */
  saveChatState() {
    saveChatState();
  }

  /**
   * Get current session ID.
   * @returns {string}
   */
  getSessionId() {
    return this.sessionId;
  }

  /**
   * Get chat history.
   * @returns {Array}
   */
  getHistory() {
    return this.history;
  }
}

// Re-export utilities for convenience
export { escapeHtml, formatMessage, addMessage, showTypingIndicator };
