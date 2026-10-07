/**
 * Feedback Bubble
 * Floating button + panel for anonymous feedback submission.
 * Inserts into the map page and posts to /api/feedback via msgpack.
 */

import { postMsgpack } from './utils/fetch.js';
import { getCurrentUser } from './auth.js';

const MAX_CHARS = 2000;

function createBubble() {
  // Button
  const btn = document.createElement('button');
  btn.id = 'feedbackBtn';
  btn.className = 'feedback-btn';
  btn.textContent = 'Feedback';
  btn.setAttribute('aria-label', 'Open feedback form');
  btn.setAttribute('title', 'Share feedback');

  // Panel
  const panel = document.createElement('div');
  panel.id = 'feedbackPanel';
  panel.className = 'feedback-panel';
  panel.setAttribute('aria-hidden', 'true');
  panel.innerHTML = `
    <div class="feedback-panel-header">
      <span class="feedback-panel-title">Share Your Thoughts</span>
      <button class="feedback-close" id="feedbackClose" aria-label="Close">&times;</button>
    </div>
    <p class="feedback-panel-copy">We are a small team building this for you. Any feedback helps - good, bad, or wishlist ideas.</p>
    <textarea id="feedbackText" class="feedback-textarea" maxlength="${MAX_CHARS}" placeholder="Anything at all is helpful..."></textarea>
    <div class="feedback-footer">
      <span id="feedbackCharCount" class="feedback-char-count">${MAX_CHARS} left</span>
      <div class="feedback-actions">
        <span id="feedbackStatus" class="feedback-status"></span>
        <button id="feedbackSubmit" class="feedback-submit">Send</button>
      </div>
    </div>
  `;

  document.body.appendChild(btn);
  document.body.appendChild(panel);

  const textarea = panel.querySelector('#feedbackText');
  const status = panel.querySelector('#feedbackStatus');
  const charCount = panel.querySelector('#feedbackCharCount');
  const submitBtn = panel.querySelector('#feedbackSubmit');
  const closeBtn = panel.querySelector('#feedbackClose');

  // Char counter
  textarea.addEventListener('input', () => {
    const remaining = MAX_CHARS - textarea.value.length;
    charCount.textContent = `${remaining} left`;
    charCount.classList.toggle('feedback-char-warn', remaining < 100);
  });

  // Toggle open/close
  function open() {
    panel.classList.add('open');
    panel.setAttribute('aria-hidden', 'false');
    btn.classList.add('active');
    textarea.focus();
  }

  function close() {
    panel.classList.remove('open');
    panel.setAttribute('aria-hidden', 'true');
    btn.classList.remove('active');
  }

  btn.addEventListener('click', () => {
    panel.classList.contains('open') ? close() : open();
  });

  closeBtn.addEventListener('click', close);

  // Click outside closes
  document.addEventListener('click', (e) => {
    if (!panel.contains(e.target) && e.target !== btn) {
      close();
    }
  });

  // ESC closes
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && panel.classList.contains('open')) {
      close();
    }
  });

  // Submit
  submitBtn.addEventListener('click', async () => {
    const message = textarea.value.trim();
    if (!message) {
      status.textContent = 'Write something first.';
      status.className = 'feedback-status error';
      return;
    }

    submitBtn.disabled = true;
    status.textContent = 'Sending...';
    status.className = 'feedback-status';

    try {
      const user = getCurrentUser();
      const payload = { message };
      if (user?.id) payload.user_id = user.id;
      await postMsgpack('/api/feedback', payload);
      textarea.value = '';
      charCount.textContent = `${MAX_CHARS} left`;
      status.textContent = 'Thank you!';
      status.className = 'feedback-status success';
      setTimeout(close, 1800);
    } catch (err) {
      status.textContent = 'Could not send right now.';
      status.className = 'feedback-status error';
    } finally {
      submitBtn.disabled = false;
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', createBubble);
} else {
  createBubble();
}
