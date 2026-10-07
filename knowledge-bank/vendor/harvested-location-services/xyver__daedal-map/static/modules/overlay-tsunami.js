import EventAnimator, { AnimationMode } from './event-animator.js';
import { beginFocusedAnimationSession } from './overlay-disaster-common.js';

export function handleTsunamiRunups(controller, data, deps) {
  const { MapAdapter, TimeSlider, dataCache, yearRangeCache } = deps;
  const { geojson, eventId, runupCount } = data;
  const overlaysToRestore = controller.captureFocusedOverlayIds?.(['tsunamis']) || ['tsunamis'];
  const session = beginFocusedAnimationSession(controller, overlaysToRestore, {
    entryDurationMs: 1500
  });
  console.log(`OverlayController: Starting tsunami runups animation for ${eventId} with ${runupCount} runups`);
  if (!geojson?.features || geojson.features.length < 2) return console.warn('OverlayController: Not enough data for tsunami animation');
  const sourceEvent = geojson.features.find(f => f.properties?.is_source === true);
  const sourceCoords = sourceEvent?.geometry?.coordinates;
  if (!sourceCoords) return console.warn('OverlayController: No source event found in tsunami data');
  MapAdapter?.hidePopup?.();
  MapAdapter.popupLocked = false;
  const sourceYear = sourceEvent.properties?.year || new Date().getFullYear();
  const sourceDate = sourceEvent.properties?.timestamp ? new Date(sourceEvent.properties.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : sourceYear;
  const started = EventAnimator.start({
    id: `tsunami-${eventId}`,
    label: `Tsunami ${sourceDate} — propagation`,
    mode: AnimationMode.RADIAL,
    events: geojson.features,
    eventType: 'tsunami',
    timeField: 'timestamp',
    granularity: '12m',
    renderer: 'point-radius',
    rendererOptions: { eventType: 'tsunami' },
    // Match earthquake focused sequences: let the entry transition settle,
    // then start the propagation automatically instead of requiring another
    // play/click action from the user.
    center: { lon: sourceCoords[0], lat: sourceCoords[1] },
    zoom: 7,
    autoPlay: true,
    autoPlayDelayMs: session.autoPlayDelayMs,
    // This is a source-to-runup explanation. Keep reached runups visible
    // through the terminal hold instead of fading early observations away.
    useFade: false,
    onExit: () => {
      session.restore();
    }
  });
  if (!started) {
    session.restore();
  }
}
