/**
 * Named, lane-scoped entry presets for short durable URLs.
 *
 * A preset is an authored entry adjustment, not saved user state. Keep it
 * small and declarative: durable pack/feed ids plus an optional map focus.
 * The same slug is intentionally allowed to mean different things per lane.
 */

const VIEW_PRESETS = Object.freeze({
  explore: Object.freeze({
    ring_of_fire: Object.freeze({
      label: 'Ring of Fire hazards',
      pack_ids: Object.freeze(['earthquakes', 'volcanoes', 'tsunamis']),
      focus: Object.freeze({ type: 'point', lat: 10, lon: -160 })
    })
  }),
  ops: Object.freeze({
    ring_of_fire: Object.freeze({
      label: 'Ring of Fire live watch',
      feed_ids: Object.freeze(['earthquakes', 'volcanoes', 'tsunamis']),
      focus: Object.freeze({ type: 'point', lat: 10, lon: -160 })
    })
  }),
  research: Object.freeze({
    ring_of_fire: Object.freeze({
      label: 'Ring of Fire research corpus',
      pack_ids: Object.freeze(['earthquakes', 'volcanoes', 'tsunamis'])
    })
  })
});

function normalizeViewId(value) {
  return String(value || '').trim().toLowerCase();
}

function cloneStringList(value) {
  return Array.isArray(value) ? value.map((item) => String(item || '').trim()).filter(Boolean) : [];
}

/**
 * Resolve a public `view=` slug for one lane.  Return a fresh object so route
 * parsing never mutates the authored table.
 */
export function resolveRouteViewPreset(lane, viewId) {
  const normalizedLane = String(lane || '').trim().toLowerCase();
  const normalizedViewId = normalizeViewId(viewId);
  const preset = VIEW_PRESETS[normalizedLane]?.[normalizedViewId];
  if (!preset) return null;
  return {
    id: normalizedViewId,
    label: String(preset.label || normalizedViewId),
    pack_ids: cloneStringList(preset.pack_ids),
    feed_ids: cloneStringList(preset.feed_ids),
    focus: preset.focus ? { ...preset.focus } : null
  };
}

export function listRouteViewPresets(lane) {
  const normalizedLane = String(lane || '').trim().toLowerCase();
  return Object.keys(VIEW_PRESETS[normalizedLane] || {}).map((viewId) =>
    resolveRouteViewPreset(normalizedLane, viewId)
  ).filter(Boolean);
}
