/**
 * Warning confirmation and resend helpers for chat flows.
 */

export function isResearchDisplayConfirmation(query) {
  const normalized = String(query || '').trim().toLowerCase();
  if (!normalized) return false;
  return [
    'yes',
    'yes, show all',
    'yes, load it anyway',
    'load it anyway',
    'show it anyway',
    'do it anyway',
    'go ahead',
    'proceed',
    'continue'
  ].includes(normalized);
}

export async function resendWithForce(ctx, deps = {}) {
  const sendStreamingRequest = deps.sendStreamingRequest;
  if (typeof sendStreamingRequest !== 'function') {
    throw new Error('sendStreamingRequest dependency is required');
  }
  if (!ctx.lastQuery) return;

  const requestMode = ctx.mode;
  if (ctx.modeRequestInFlight[requestMode]) return;
  ctx.modeRequestInFlight[requestMode] = true;
  ctx.updateComposerState();

  const indicator = ctx.showTypingIndicator(true);

  try {
    const payload = ctx.buildPayload(ctx.lastQuery, null, { force_metrics: true });
    const response = await sendStreamingRequest(payload, (stage, message) => {
      indicator.updateStage(stage, message);
    });

    if (response) {
      ctx.history.push({ role: 'assistant', content: response.message || response.summary });
      ctx.handleResponse(response);
    }
  } catch (error) {
    console.error('Force metrics re-send error:', error);
    ctx.addMessage('Sorry, something went wrong. Please try again.', 'assistant');
  } finally {
    indicator.remove();
    ctx.modeRequestInFlight[requestMode] = false;
    ctx.updateComposerState();
    ctx.elements.input?.focus();
  }
}

export async function resendWithResearchDisplayForce(ctx, deps = {}) {
  const sendStreamingRequest = deps.sendStreamingRequest;
  if (typeof sendStreamingRequest !== 'function') {
    throw new Error('sendStreamingRequest dependency is required');
  }
  if (!ctx.pendingResearchDisplayWarning?.overrideAllowed) return;

  const requestMode = ctx.mode;
  if (ctx.modeRequestInFlight[requestMode]) return;
  ctx.modeRequestInFlight[requestMode] = true;
  ctx.updateComposerState();

  const indicator = ctx.showTypingIndicator(true, requestMode);

  try {
    if (requestMode !== 'research' && ctx.pendingDisplayOrder) {
      await ctx.executeOrder(ctx.pendingDisplayOrder, { forceLargeDisplay: true });
      ctx.pendingDisplayOrder = null;
      ctx.pendingResearchDisplayWarning = null;
      return;
    }
    if (!ctx.lastQuery) return;
    const payload = ctx.buildPayload(
      ctx.lastQuery,
      null,
      { force_research_display: true },
      requestMode
    );
    const endpoint = requestMode === 'research'
      ? '/chat/research/stream'
      : requestMode === 'ops'
        ? '/chat/ops/stream'
        : '/chat/stream';
    const response = await sendStreamingRequest(payload, (stage, message, deltaText, rawEvent) => {
      if (stage === 'display' && rawEvent?.map_payload) {
        const mapPayload = ctx.decorateResearchDisplay(rawEvent.map_payload, {
          rasterMode: ctx.pendingResearchRasterMode
        });
        ctx.applySupplementalChatActions(mapPayload);
        return;
      }
      indicator.updateStage(stage, message);
    }, endpoint);

    if (response) {
      ctx.pendingResearchDisplayWarning = null;
      ctx.history.push({ role: 'assistant', content: response.message || response.summary });
      ctx.handleResponse({
        ...ctx.decorateResearchResponse(response, {
          rasterMode: ctx.pendingResearchRasterMode
        }),
        _requestMode: requestMode
      });
    }
  } catch (error) {
    console.error('Force research display re-send error:', error);
    ctx.addMessage('Sorry, something went wrong. Please try again.', 'assistant', { mode: requestMode });
  } finally {
    ctx.pendingResearchRasterMode = null;
    indicator.remove();
    ctx.modeRequestInFlight[requestMode] = false;
    ctx.updateComposerState();
    ctx.elements.input?.focus();
  }
}
