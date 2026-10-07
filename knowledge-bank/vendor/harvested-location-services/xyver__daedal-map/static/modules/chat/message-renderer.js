/**
 * Chat Message Renderer
 * Handles rendering messages, typing indicators, and text formatting.
 * Reusable across map app and admin dashboard.
 */

/**
 * Escape HTML to prevent XSS.
 * @param {string} text - Raw text to escape
 * @returns {string} HTML-safe string
 */
export function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Format assistant message text with basic markdown.
 * Supports bold (**text**), markdown tables, newlines, and inline formatting.
 * @param {string} text - Raw message text
 * @returns {string} Formatted HTML string
 */
function formatInline(text) {
  let formatted = escapeHtml(text);
  formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  formatted = formatted.replace(/__(.+?)__/g, '<strong>$1</strong>');
  return formatted;
}

function isTableSeparatorLine(line) {
  const trimmed = String(line || '').trim();
  if (!trimmed.includes('-')) return false;
  const cells = trimmed
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map(cell => cell.trim());
  if (!cells.length) return false;
  return cells.every(cell => /^:?-{3,}:?$/.test(cell));
}

function splitTableCells(line) {
  return String(line || '')
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map(cell => cell.trim());
}

function buildTableHtml(headerLine, bodyLines) {
  const headers = splitTableCells(headerLine);
  const rows = bodyLines
    .map(splitTableCells)
    .filter(cells => cells.length && cells.some(cell => cell.length > 0));
  if (!headers.length || !rows.length) return null;
  const thead = `<thead><tr>${headers.map(cell => `<th>${formatInline(cell)}</th>`).join('')}</tr></thead>`;
  const tbody = `<tbody>${rows.map(cells => `<tr>${cells.map(cell => `<td>${formatInline(cell)}</td>`).join('')}</tr>`).join('')}</tbody>`;
  return `<div class="chat-table-wrap"><table class="chat-table">${thead}${tbody}</table></div>`;
}

function isUnorderedListLine(line) {
  return /^\s*[-*]\s+/.test(String(line || ''));
}

function isOrderedListLine(line) {
  return /^\s*\d+\.\s+/.test(String(line || ''));
}

function stripListMarker(line, ordered = false) {
  return ordered
    ? String(line || '').replace(/^\s*\d+\.\s+/, '')
    : String(line || '').replace(/^\s*[-*]\s+/, '');
}

function buildListHtml(lines, ordered = false) {
  const tag = ordered ? 'ol' : 'ul';
  const items = lines
    .map(line => stripListMarker(line, ordered))
    .filter(line => String(line || '').trim().length > 0)
    .map(line => `<li>${formatInline(line)}</li>`)
    .join('');
  if (!items) return null;
  return `<${tag} class="chat-list chat-list--${ordered ? 'ordered' : 'unordered'}">${items}</${tag}>`;
}

export function formatMessage(text) {
  const lines = String(text || '').replace(/\r\n/g, '\n').split('\n');
  const output = [];

  for (let i = 0; i < lines.length; i += 1) {
    const current = lines[i] || '';
    const next = lines[i + 1] || '';
    if (current.includes('|') && isTableSeparatorLine(next)) {
      const bodyLines = [];
      let j = i + 2;
      while (j < lines.length && String(lines[j] || '').includes('|')) {
        bodyLines.push(lines[j]);
        j += 1;
      }
      const tableHtml = buildTableHtml(current, bodyLines);
      if (tableHtml) {
        output.push(tableHtml);
        i = j - 1;
        continue;
      }
    }

    if (isUnorderedListLine(current) || isOrderedListLine(current)) {
      const ordered = isOrderedListLine(current);
      const listLines = [current];
      let j = i + 1;
      while (j < lines.length) {
        const line = lines[j] || '';
        if (ordered ? isOrderedListLine(line) : isUnorderedListLine(line)) {
          listLines.push(line);
          j += 1;
          continue;
        }
        break;
      }
      const listHtml = buildListHtml(listLines, ordered);
      if (listHtml) {
        output.push(listHtml);
        i = j - 1;
        continue;
      }
    }

    output.push(formatInline(current));
  }

  return output.join('<br>');
}

/**
 * Add a message to the chat container.
 * @param {HTMLElement} container - The messages container element
 * @param {string} text - Message text
 * @param {string} type - 'user' or 'assistant'
 * @param {Object} options - { html, className, dataset, prepend } helpers
 * @returns {HTMLElement} The created message div
 */
export function addMessage(container, text, type, options = {}) {
  const div = document.createElement('div');
  div.className = `chat-message ${type}`;
  if (options.className) {
    div.className += ` ${String(options.className).trim()}`;
  }
  if (options.dataset && typeof options.dataset === 'object') {
    for (const [key, value] of Object.entries(options.dataset)) {
      if (value == null) continue;
      div.dataset[key] = String(value);
    }
  }

  if (options.html) {
    div.innerHTML = text;
  } else if (type === 'assistant') {
    div.innerHTML = formatMessage(text);
  } else {
    div.textContent = text;
  }

  if (options.prepend && container.firstChild) {
    container.insertBefore(div, container.firstChild);
  } else {
    container.appendChild(div);
  }
  container.scrollTop = container.scrollHeight;

  return div;
}

/**
 * Show a typing/loading indicator in the chat.
 * @param {HTMLElement} container - The messages container element
 * @param {boolean} staged - If true, show staged indicator with text updates
 * @returns {HTMLElement} Indicator element with updateStage(stage, message) method
 */
export function showTypingIndicator(container, staged = false) {
  const indicator = document.createElement('div');
  indicator.className = staged ? 'loading-indicator' : 'typing-indicator';

  if (staged) {
    indicator.innerHTML = `
      <div class="loading-spinner"></div>
      <span class="loading-text">Processing...</span>
    `;
    indicator.dataset.stage = 'initial';

    indicator.updateStage = (stage, message) => {
      indicator.dataset.stage = stage;
      const textEl = indicator.querySelector('.loading-text');
      if (textEl) textEl.textContent = message;
    };
  } else {
    indicator.innerHTML = '<span></span><span></span><span></span>';
    indicator.updateStage = () => {};  // no-op for non-staged
  }

  container.appendChild(indicator);
  container.scrollTop = container.scrollHeight;
  return indicator;
}
