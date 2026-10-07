import EventAnimator, { AnimationMode } from './event-animator.js';
import { beginFocusedAnimationSession, selectEarthquakeSequenceFeatures } from './overlay-disaster-common.js';

export async function handleSequenceChange(controller, sequenceId, eventId, deps) {
  const { ModelRegistry, OverlaySelector, OVERLAY_ENDPOINTS, TimeSlider, dataCache, yearRangeCache, gardnerKnopoffTimeWindow, fetchMsgpack } = deps;
  const VIEWPORT_DURATION_MS = 1500;
  if (EventAnimator.getIsActive()) EventAnimator.stop();
  if (!sequenceId && !eventId) {
    controller.restoreViewState?.(controller.captureViewState?.(), ['earthquakes']);
    return;
  }
  const cacheKey = eventId || sequenceId;
  let seqEvents;
  try {
    let endpoint;
    if (eventId) endpoint = `/api/earthquakes/aftershocks/${encodeURIComponent(eventId)}`;
    else endpoint = `/api/earthquakes/sequence/${encodeURIComponent(sequenceId)}`;
    const data = await fetchMsgpack(endpoint);
    seqEvents = data.features || [];
  } catch (error) {
    console.error('OverlayController: Error fetching sequence data:', error);
    return;
  }
  if (!seqEvents.length) return console.warn(`OverlayController: No events found for sequence ${cacheKey}`);
  const selectedSequence = selectEarthquakeSequenceFeatures(seqEvents);
  seqEvents = selectedSequence.selectedFeatures;
  const mainshock = selectedSequence.mainshockFeature;
  if (!mainshock) return console.warn(`OverlayController: Could not identify mainshock for sequence ${cacheKey}`);
  const mainMag = mainshock.properties.magnitude || 5.5;
  const mainTime = new Date(mainshock.properties.timestamp || mainshock.properties.time).getTime();
  const windowEnd = mainTime + gardnerKnopoffTimeWindow(mainMag) * 24 * 60 * 60 * 1000;
  let minTime = mainTime;
  let maxTime = mainTime;
  for (const event of seqEvents) {
    const t = new Date(event.properties.timestamp || event.properties.time).getTime();
    if (t < minTime) minTime = t;
    if (t > maxTime) maxTime = t;
  }
  maxTime = Math.max(maxTime, windowEnd);
  const timeRange = maxTime - minTime;
  const stepHours = Math.max(1, Math.ceil((timeRange / (60 * 60 * 1000)) / 200));
  let granularityLabel = '6h';
  if (stepHours < 2) granularityLabel = '1h';
  else if (stepHours < 4) granularityLabel = '2h';
  else if (stepHours < 8) granularityLabel = '6h';
  else if (stepHours < 16) granularityLabel = '12h';
  else if (stepHours < 36) granularityLabel = 'daily';
  else granularityLabel = '2d';
  const label = `M${mainMag.toFixed(1)} ${new Date(mainTime).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;
  const activeOverlays = OverlaySelector?.getActiveOverlays() || [];
  const overlaysToRestore = activeOverlays.filter(id => id !== 'demographics' && OVERLAY_ENDPOINTS[id]);
  const session = beginFocusedAnimationSession(controller, overlaysToRestore, {
    entryDurationMs: VIEWPORT_DURATION_MS
  });
  const model = ModelRegistry?.getModelForType('earthquake');
  if (model?.clear) model.clear();
  EventAnimator.start({
    id: `seq-${String(cacheKey || 'earthquake').replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 12)}`,
    label,
    mode: AnimationMode.EARTHQUAKE,
    events: seqEvents,
    mainshock,
    eventType: 'earthquake',
    timeField: 'timestamp',
    granularity: granularityLabel,
    renderer: 'point-radius',
    autoPlay: true,
    autoPlayDelayMs: session.autoPlayDelayMs,
    onExit: () => {
      session.restore();
    }
  });
}
