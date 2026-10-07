/**
 * Lane switching and chat-mode UI helpers.
 */

import { isSharedShellRoute, writeLane, setLaneTitle } from '../routing/app-route-state.js';

function normalizeChatMode(mode, chatModes = ['explore', 'research', 'ops']) {
  return chatModes.includes(mode) ? mode : 'explore';
}

function paneHasMessages(pane) {
  if (!pane) return false;
  if (pane.querySelector('.chat-message')) return true;
  return String(pane.textContent || '').trim().length > 0;
}

function paneHasWelcomeMessage(pane) {
  if (!pane) return false;
  return Boolean(
    pane.querySelector('[data-welcome-kind="intro"]')
    || pane.querySelector('[data-welcome-message="true"]')
  );
}

function paneHasWelcomeStatus(pane) {
  if (!pane) return false;
  return Boolean(pane.querySelector('[data-welcome-kind="status"], [data-welcome-status="true"]'));
}

function clearWelcomeMessages(pane) {
  if (!pane) return;
  pane.querySelectorAll('[data-welcome-message="true"], [data-welcome-status="true"], [data-welcome-kind]').forEach((node) => {
    node.remove();
  });
}

function addAssistantMessageIfPresent(ctx, text, options = {}) {
  const content = String(text || '').trim();
  if (!content) return;
  ctx.addMessage(content, 'assistant', {
    ...options,
    skipAssistantDedup: true
  });
}

export async function switchChatMode(ctx, mode, deps = {}) {
  const App = deps.App || null;
  const OverlaySelector = deps.OverlaySelector || null;
  const chatModes = deps.CHAT_MODES || ['explore', 'research', 'ops'];
  const sharedShell = isSharedShellRoute();
  mode = normalizeChatMode(mode, chatModes);
  if (mode === ctx.mode) return;

  ctx.syncModeMessagesHtml(ctx.mode);
  ctx.modeHistories[ctx.mode] = ctx.history;

  ctx.mode = mode;
  // Keep the shared shell at '/' when the selector is used there; lane-specific
  // URLs still remain stable when entered directly or shared as deep links.
  if (!isSharedShellRoute()) {
    writeLane(mode);
  }
  setLaneTitle(mode);
  ctx.history = ctx.modeHistories[mode] || [];
  applyModeUiState(ctx, deps);
  App?.activateLaneMapView?.(mode);

  if (mode === 'research') {
    await ctx.refreshResearchCorpusOptions();
  } else if (mode === 'ops') {
    try {
      await ctx.refreshOpsReport({ loadWatch: true });
      OverlaySelector?.refreshVisibility?.();
    } catch (error) {
      console.warn('Ops report refresh failed:', error);
    }
  }

  const pane = ctx.messagePanes?.[mode] || null;
  const laneHistory = Array.isArray(ctx.modeHistories?.[mode]) ? ctx.modeHistories[mode] : [];
  const shouldReseedForSharedShell = sharedShell && laneHistory.length === 0;
  if (shouldReseedForSharedShell) {
    clearWelcomeMessages(pane);
  }
  if (
    !paneHasWelcomeMessage(pane)
    || !paneHasWelcomeStatus(pane)
  ) {
    await seedEmptyConversation(ctx, mode, deps);
  }

  applyModeUiState(ctx, deps);
  ctx.saveState();
}

export async function seedEmptyConversation(ctx, mode = ctx.mode, deps = {}) {
  const buildExploreWelcomeMessage = deps.buildExploreWelcomeMessage || (() => '');
  const buildExploreWelcomeStatusMessage = deps.buildExploreWelcomeStatusMessage || (() => '');
  const buildResearchFriendlyWelcomeMessage = deps.buildResearchFriendlyWelcomeMessage || (() => '');
  const buildResearchWelcomeMessage = deps.buildResearchWelcomeMessage || ((_manifest, fallback) => fallback || '');
  const buildOpsFriendlyWelcomeMessage = deps.buildOpsFriendlyWelcomeMessage || (() => '');
  const buildOpsWelcomeMessage = deps.buildOpsWelcomeMessage || ((payload, fallback) => payload?.warning || fallback || '');
  const pane = ctx.messagePanes?.[mode];
  const hasIntro = paneHasWelcomeMessage(pane);
  const hasStatus = paneHasWelcomeStatus(pane);
  if (hasIntro && hasStatus) return;
  if (hasIntro || hasStatus) {
    clearWelcomeMessages(pane);
  }
  const welcomeOptions = {
    mode,
    prepend: paneHasMessages(pane),
    className: 'chat-message--welcome',
    dataset: { welcomeMessage: 'true', welcomeKind: 'intro', lane: mode }
  };

  if (mode === 'research') {
    try {
      if (!Array.isArray(ctx.researchCorpusOptions) || ctx.researchCorpusOptions.length === 0) {
        await ctx.refreshResearchCorpusOptions();
      }
      const manifest = ctx.latestResearchManifest || await ctx.refreshResearchManifest();
      addAssistantMessageIfPresent(
        ctx,
        buildResearchFriendlyWelcomeMessage(),
        { ...welcomeOptions, html: true }
      );
      addAssistantMessageIfPresent(
        ctx,
        buildResearchWelcomeMessage(manifest, ctx.getResearchEmptyStateMessage()),
        { mode, className: 'chat-message--welcome', dataset: { welcomeStatus: 'true', welcomeKind: 'status', lane: mode }, html: true }
      );
    } catch (error) {
      console.warn('Research corpus manifest check failed:', error);
      ctx.addMessage('Research mode is available, but I could not read the active corpus yet.', 'assistant', welcomeOptions);
    }
    return;
  }

  if (mode === 'ops') {
    try {
      const payload = ctx.latestOpsPayload
        ? ctx.latestOpsPayload
        : await ctx.refreshOpsReport({ loadWatch: true });
      addAssistantMessageIfPresent(
        ctx,
        buildOpsFriendlyWelcomeMessage(),
        { ...welcomeOptions, html: true }
      );
      addAssistantMessageIfPresent(
        ctx,
        buildOpsWelcomeMessage(payload, ctx.getOpsEmptyStateMessage()),
        { mode, className: 'chat-message--welcome', dataset: { welcomeStatus: 'true', welcomeKind: 'status', lane: mode }, html: true }
      );
    } catch (error) {
      console.warn('Ops report check failed:', error);
      ctx.addMessage('Ops mode is available, but I could not read the active watch yet.', 'assistant', welcomeOptions);
    }
    return;
  }

  addAssistantMessageIfPresent(
    ctx,
    buildExploreWelcomeMessage(),
    { ...welcomeOptions, html: true }
  );
  addAssistantMessageIfPresent(
    ctx,
    buildExploreWelcomeStatusMessage(),
    { mode, className: 'chat-message--welcome', dataset: { welcomeStatus: 'true', welcomeKind: 'status', lane: mode } }
  );
}

export function applyModeUiState(ctx, deps = {}) {
  const researchModeToggle = deps.researchModeToggle || null;
  const OverlaySelector = deps.OverlaySelector || null;
  updateSidebarModeLayout(ctx);
  if (researchModeToggle) {
    researchModeToggle.mode = ctx.mode;
    researchModeToggle.setSelectedCorpusId(ctx.selectedResearchCorpusId);
    researchModeToggle.updateActive();
  }
  ctx.setActiveMessagePane(ctx.mode);
  ctx.updateResearchCorpusStatus();
  OverlaySelector?.syncToCurrentMode?.();
  if (ctx.mode === 'ops') {
    OverlaySelector?.expand?.();
  }
  // Ops mode is "what's happening now" - there is no historical time window, so
  // enabling an overlay should not pop the time slider / animation bar. Suppress
  // (and hide) it in Ops; allow it again in Explore/Research.
  const overlayController = window.OverlayController || null;
  if (overlayController?.setTimelineAutoShowSuppressed) {
    const inOps = ctx.mode === 'ops';
    overlayController.setTimelineAutoShowSuppressed(inOps, { hide: inOps });
  }
  const tickerController = window.TickerController || null;
  if (tickerController?.setEnabled) {
    tickerController.setEnabled(ctx.mode === 'ops');
  }
  updateComposerState(ctx);
}

export function updateComposerState(ctx) {
  const { input, sendBtn } = ctx.elements;
  const disabled = !!ctx.modeRequestInFlight?.[ctx.mode];
  if (sendBtn) sendBtn.disabled = disabled;
  if (input) input.disabled = disabled;
}

export function syncSidebarToggleVisibility(ctx) {
  const { sidebar, toggle } = ctx.elements;
  if (!sidebar || !toggle) return;
  toggle.style.display = sidebar.classList.contains('collapsed') ? 'flex' : 'none';
}

export function updateSidebarModeLayout(ctx) {
  const { orderPanel, resizeOrder, form } = ctx.elements;
  const hideOrderTaker = ctx.mode === 'research'
    || ctx.mode === 'ops'
    || (ctx.mode === 'explore' && !ctx.isExploreOrderTakerEnabled?.());
  const container = document.getElementById('chatContainer');
  document.body.classList.toggle('chat-mode-research', ctx.mode === 'research');
  document.body.classList.toggle('chat-mode-ops', ctx.mode === 'ops');
  document.body.classList.toggle('chat-mode-explore', ctx.mode === 'explore');
  if (container) {
    container.classList.toggle('chat-container--research', ctx.mode === 'research');
    container.classList.toggle('chat-container--ops', ctx.mode === 'ops');
    container.classList.toggle('chat-container--explore', ctx.mode === 'explore');
  }
  if (orderPanel) {
    orderPanel.hidden = hideOrderTaker;
    orderPanel.setAttribute('aria-hidden', hideOrderTaker ? 'true' : 'false');
    orderPanel.style.display = hideOrderTaker ? 'none' : '';
  }
  if (resizeOrder) {
    resizeOrder.hidden = hideOrderTaker;
    resizeOrder.setAttribute('aria-hidden', hideOrderTaker ? 'true' : 'false');
    resizeOrder.style.display = hideOrderTaker ? 'none' : '';
  }
  if (form) {
    form.setAttribute('data-chat-mode', ctx.mode);
  }
  enforceResearchUiBoundaries(ctx);
}

export function enforceResearchUiBoundaries(ctx) {
  const hideOrderTaker = ctx.mode === 'research'
    || ctx.mode === 'ops'
    || (ctx.mode === 'explore' && !ctx.isExploreOrderTakerEnabled?.());
  const { orderPanel, resizeOrder } = ctx.elements;
  const container = document.getElementById('chatContainer');
  document.body.classList.toggle('chat-mode-research', ctx.mode === 'research');
  document.body.classList.toggle('chat-mode-ops', ctx.mode === 'ops');
  document.body.classList.toggle('chat-mode-explore', ctx.mode === 'explore');
  if (container) {
    container.classList.toggle('chat-container--research', ctx.mode === 'research');
    container.classList.toggle('chat-container--ops', ctx.mode === 'ops');
    container.classList.toggle('chat-container--explore', ctx.mode === 'explore');
  }
  for (const element of [orderPanel, resizeOrder]) {
    if (!element) continue;
    element.hidden = hideOrderTaker;
    element.setAttribute('aria-hidden', hideOrderTaker ? 'true' : 'false');
    element.style.display = hideOrderTaker ? 'none' : '';
    element.style.visibility = hideOrderTaker ? 'hidden' : '';
    element.style.pointerEvents = hideOrderTaker ? 'none' : '';
  }
}
