/**
 * Chat response routing helpers.
 */

import { getSiteBaseUrl } from '../auth.js';
import { AuroraOverlay } from '../overlay-aurora.js';
import { routeMapPayloadContract } from './chat-response-routing-contract.mjs';

export function routeMapResponse(ctx, response, options = {}, deps = {}) {
  return routeMapPayloadContract(ctx, response, options, deps);
}

export function applyFilterUpdate(ctx, response, deps = {}) {
  const OverlayController = deps.OverlayController || null;
  const { overlay, filters } = response;

  if (!OverlayController) {
    console.warn('OverlayController not available for filter update');
    return;
  }

  if (filters.clear) {
    OverlayController.clearFilters?.(overlay);
  } else {
    OverlayController.updateFilters?.(overlay, filters);
  }

  OverlayController.reloadOverlay?.(overlay);
}

function formatChatError(response) {
  const parts = [];
  const message = String(response?.message || '').trim();
  const retryHint = String(response?.retry_hint || '').trim();
  const errorCode = String(response?.error_code || '').trim();
  const requestId = String(response?.request_id || '').trim();

  if (message) {
    parts.push(message);
  } else {
    parts.push('An error occurred.');
  }
  if (retryHint) {
    parts.push(`Next step: ${retryHint}`);
  }
  if (errorCode) {
    parts.push(`Code: ${errorCode}`);
  }
  if (requestId) {
    parts.push(`Request id: ${requestId}`);
  }
  return parts.join('\n\n');
}

function appendErrorCta(messageEl, response) {
  if (!messageEl || !response || response.type !== 'error') return;
  const cta = String(response.cta || '').trim().toLowerCase();
  if (cta !== 'sign_up' && cta !== 'top_up') return;

  const rawUrl = String(response.cta_url || '').trim();
  const siteBase = String(getSiteBaseUrl() || '').trim();
  const ctaUrl = rawUrl
    ? (rawUrl.startsWith('http://') || rawUrl.startsWith('https://')
        ? rawUrl
        : `${siteBase}${rawUrl.startsWith('/') ? rawUrl : `/${rawUrl}`}`)
    : '/settings';
  const ctaLabel = String(response.cta_label || '').trim()
    || 'Open settings';

  const container = document.createElement('div');
  container.className = 'metric-warning-buttons';
  const link = document.createElement('a');
  link.className = 'chat-action-btn confirm';
  link.href = ctaUrl;
  link.target = '_blank';
  link.rel = 'noopener';
  link.textContent = ctaLabel;
  container.appendChild(link);
  messageEl.appendChild(container);
}

export function handleResponse(ctx, response, deps = {}) {
  const {
    App = null,
    OverlayController = null,
    OverlaySelector = null,
    SelectionManager = null,
    TutorialMode = null,
    SavedOrders = null,
    orderPanel = null
  } = deps;

  const targetMode = response?._requestMode || ctx.mode;
  const suppressAssistantMessage = response?._suppressAssistantMessage === true;
  if (targetMode === 'research' || ctx.mode === 'research') {
    ctx.enforceResearchUiBoundaries();
  }
  const add = (text, type = 'assistant', options = {}) => {
    if (suppressAssistantMessage && type === 'assistant') {
      return document.createElement('div');
    }
    return ctx.addMessage(text, type, { ...options, mode: targetMode });
  };
  switch (response.type) {
    case 'overlay_range_load': {
      const action = {
        type: 'overlay_range_load',
        overlayId: response.overlay_id,
        startMs: response.start_ms,
        endMs: response.end_ms,
      };
      add(response.message || 'Loading the requested map range.', 'assistant');
      Promise.resolve(ctx.executeDefaultLoadAction?.(action, {
        mode: targetMode,
        suppressResultMessage: true,
      })).then((loaded) => {
        if (!loaded) add('That map range could not be loaded. Try a smaller time window.', 'assistant');
      }).catch((error) => {
        console.error('Overlay range load failed:', error);
        const detail = String(error?.message || '').trim();
        add(
          detail
            ? `That map range could not be loaded: ${detail}`
            : 'That map range could not be loaded. Try a smaller time window.',
          'assistant'
        );
      });
      break;
    }

    case 'order':
      ctx.pendingMetricOrder = null;
      if (targetMode === 'explore' && !ctx.isExploreOrderTakerEnabled?.()) {
        Promise.resolve(
          ctx.executeOrder?.(response.full_order || response.order, { mode: targetMode })
        ).catch((error) => {
          console.error('Auto-execute explore order failed:', error);
          add('Sorry, I could not display that on the map.', 'assistant');
        });
      } else {
        add('Added to your order. Click "Display on Map" when ready.', 'assistant');
        orderPanel.setOrder(response.order, response.summary, response.full_order || response.order);
      }
      break;

    case 'already_loaded':
      add(response.message || 'This data is already loaded on your map.', 'assistant');
      if (orderPanel.switchTab) orderPanel.switchTab('loaded');
      break;

    case 'metric_warning': {
      const pendingSignature = JSON.stringify(response.pending_order || response.full_order || {});
      const existingSignature = JSON.stringify(ctx.pendingMetricOrder?.order || ctx.pendingMetricOrder?.full_order || {});
      // Streaming/retry paths can surface the same warning more than once.
      // Keep one pending decision and one pair of buttons rather than making
      // the user answer identical confirmation cards repeatedly.
      if (ctx.pendingMetricOrder && pendingSignature === existingSignature) {
        break;
      }
      ctx.pendingDisplayOrder = null;
      ctx.pendingResearchDisplayWarning = null;
      ctx.pendingMetricOrder = {
        order: response.pending_order,
        full_order: response.full_order,
        summary: response.summary
      };
      const msgEl = add(response.message, 'assistant');
      const btnContainer = document.createElement('div');
      btnContainer.className = 'metric-warning-buttons';

      const yesBtn = document.createElement('button');
      yesBtn.textContent = 'Yes, show all';
      yesBtn.className = 'chat-action-btn confirm';
      yesBtn.addEventListener('click', () => {
        btnContainer.remove();
        ctx.resendWithForce();
      });

      const noBtn = document.createElement('button');
      noBtn.textContent = 'No, let me narrow it';
      noBtn.className = 'chat-action-btn cancel';
      noBtn.addEventListener('click', () => {
        btnContainer.remove();
        add('Sure - what specific metrics would you like?', 'assistant');
      });

      btnContainer.appendChild(yesBtn);
      btnContainer.appendChild(noBtn);
      msgEl.appendChild(btnContainer);
      break;
    }

    case 'display_warning': {
      ctx.pendingMetricOrder = null;
      ctx.pendingDisplayOrder = response.pending_order || null;
      ctx.pendingResearchDisplayWarning = {
        level: response.warning_level,
        rowCount: response.row_count,
        softCap: response.soft_cap,
        hardCap: response.hard_cap,
        overrideAllowed: Boolean(response.override_allowed)
      };
      const msgEl = add(response.message, 'assistant');
      const btnContainer = document.createElement('div');
      btnContainer.className = 'metric-warning-buttons';

      if (response.override_allowed) {
        const yesBtn = document.createElement('button');
        yesBtn.textContent = 'Continue anyway';
        yesBtn.className = 'chat-action-btn confirm';
        yesBtn.addEventListener('click', () => {
          btnContainer.remove();
          ctx.resendWithResearchDisplayForce();
        });
        btnContainer.appendChild(yesBtn);
      }
      if (btnContainer.childNodes.length) {
        msgEl.appendChild(btnContainer);
      }
      break;
    }

    case 'clarify':
      ctx.pendingMetricOrder = null;
      ctx.pendingResearchDisplayWarning = null;
      add(response.message || 'Could you be more specific?', 'assistant');
      break;

    case 'disambiguate':
      add(response.message || 'Please select a location:', 'assistant');
      ctx.lastDisambiguationOptions = response.options || [];
      if (SelectionManager) {
        SelectionManager.enter(response, (selected, originalQuery) => {
          ctx.handleDisambiguationSelection(selected, originalQuery);
        });
      }
      break;

    case 'navigate':
      add(response.message || 'Showing locations.', 'assistant');
      ctx.handleNavigation(response);
      break;

    case 'drilldown':
      add(response.message || 'Loading...', 'assistant');
      if (App && response.loc_id) {
        App.drillDown(response.loc_id, response.name || response.loc_id);
      }
      break;

    case 'data':
      add(response.summary || 'Here is your data.', 'assistant');
      routeMapResponse(ctx, response, { origin: targetMode }, deps);
      break;

    case 'events':
      add(response.summary || `Showing ${response.count} ${response.event_type} events.`, 'assistant');
      routeMapResponse(ctx, response, { origin: targetMode }, deps);
      break;

    case 'cache_answer':
      add(response.message || 'Here is the current state.', 'assistant');
      break;

    case 'order_response':
      if (response.action === 'remove') {
        add(response.summary || `Removed ${response.count || 0} ${response.data_type || 'items'}.`, 'assistant');
      } else {
        add(response.summary || 'Order complete.', 'assistant');
      }
      routeMapResponse(ctx, response, { origin: targetMode }, deps);
      break;

    case 'mixed_order':
      if (response.results) {
        for (const result of response.results) {
          routeMapResponse(ctx, result, { origin: targetMode }, deps);
        }
      }
      add(response.summary || `Updated: added ${response.add_count || 0}, removed ${response.remove_count || 0}`, 'assistant');
      break;

    case 'geometry_remove':
      add(response.message || 'Removing geometry.', 'assistant');
      routeMapResponse(ctx, { ...response, action: 'remove', data_type: 'geometry' }, { origin: targetMode }, deps);
      break;

    case 'filter_update':
      add(response.message || 'Updating filters.', 'assistant');
      applyFilterUpdate(ctx, response, deps);
      break;

    case 'filter_existing':
      add(response.message || 'Filtering cached data.', 'assistant');
      if (response.overlay && response.filters && OverlayController) {
        OverlayController.updateFilters(response.overlay, response.filters);
        OverlayController.rerenderFromCache?.();
      }
      break;

    case 'overlay_toggle':
      add(response.message || (response.enabled ? 'Enabling overlay.' : 'Disabling overlay.'), 'assistant');
      if (response.overlay && OverlaySelector) {
        const isCurrentlyActive = OverlaySelector.isActive(response.overlay);
        if (response.enabled && !isCurrentlyActive) {
          OverlaySelector.toggle(response.overlay);
        } else if (!response.enabled && isCurrentlyActive) {
          OverlaySelector.toggle(response.overlay);
        }
        if (response.enabled && response.filters && OverlayController) {
          OverlayController.updateFilters(response.overlay, response.filters);
          OverlayController.reloadOverlay(response.overlay);
        }
      }
      break;

    case 'tutorial_mode': {
      const result = TutorialMode.applyCommand(response.action || (response.enabled ? 'on' : 'off'));
      add(response.message || result.message, 'assistant');
      break;
    }

    case 'address_prompt':
      ctx.showAddressPrompt(response);
      break;

    case 'save_order':
      if (response.name) {
        const saved = SavedOrders.save(
          response.name,
          orderPanel?.currentOrder?.items || [],
          orderPanel?.currentOrder?.summary || ''
        );
        if (saved) {
          add(`Order saved as "${saved.name}"`, 'assistant');
        } else {
          add('No order to save.', 'assistant');
        }
      } else {
        add('Please specify a name to save the order (e.g., "save as California Data").', 'assistant');
      }
      break;

    case 'list_orders': {
      const savedOrders = SavedOrders.getAll();
      if (savedOrders.length === 0) {
        add('No saved orders. Save an order first with "save as [name]".', 'assistant');
      } else {
        const names = savedOrders.map(o => `- ${o.name}`).join('\n');
        add(`Saved orders:\n${names}`, 'assistant');
      }
      break;
    }

    case 'load_order':
      if (response.name) {
        const order = SavedOrders.load(response.name);
        if (order && orderPanel) {
          orderPanel.currentOrder = {
            items: JSON.parse(JSON.stringify(order.items)),
            summary: order.summary || 'Loaded saved order: ' + order.name
          };
          orderPanel.render(orderPanel.currentOrder.summary);
          orderPanel.switchTab('order');
          add(`Loaded saved order: "${order.name}"`, 'assistant');
        } else if (!order) {
          add(`No saved order found with name "${response.name}".`, 'assistant');
        }
      } else {
        const allOrders = SavedOrders.getAll();
        if (allOrders.length > 0) {
          const names = allOrders.map(o => `- ${o.name}`).join('\n');
          add(`Which order? Available:\n${names}`, 'assistant');
        } else {
          add('No saved orders available.', 'assistant');
        }
      }
      break;

    case 'delete_order':
      if (response.name) {
        if (SavedOrders.deleteOrder(response.name)) {
          add(`Deleted saved order: "${response.name}"`, 'assistant');
        } else {
          add(`No saved order found with name "${response.name}".`, 'assistant');
        }
      } else {
        add('Please specify which order to delete (e.g., "delete order California Analysis").', 'assistant');
      }
      break;

    case 'error':
      appendErrorCta(add(formatChatError(response), 'assistant'), response);
      break;

    case 'chat':
    default:
      ctx.pendingMetricOrder = null;
      ctx.pendingResearchDisplayWarning = null;
      if (targetMode === 'ops' && response.ui_action === 'freeze_aurora_latest') {
        AuroraOverlay.freezeAtLatest();
      }
      ctx.applySupplementalChatActions(response);
      if (response.geojson && response.geojson.features && response.geojson.features.length > 0) {
        add(response.message || response.summary || 'Found data for you.', 'assistant');
        routeMapResponse(ctx, response, { origin: targetMode }, deps);
      } else {
        add(response.message || response.summary || 'Could you be more specific?', 'assistant');
      }
      break;
  }
}
