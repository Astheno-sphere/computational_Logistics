/**
 * Geometry Basics Popup - the `geometry_basics_popup` display family.
 *
 * Reference-geometry popups answer "what do we hold for this place, and how
 * far along is it", not "what happened here". That is a different question
 * from both the metric popup (a value belonging to a loc_id) and the disaster
 * popup (a time-bounded event), so it gets its own family rather than
 * borrowing event language for a status view.
 *
 * Started as a lightweight fork of the metric popup shell: same line-joined
 * layout, same title and muted-note idiom, none of the metric tabs, year
 * suffixes, or choropleth coupling. Build it up as geometry surfaces need
 * more, but keep it describing held geometry rather than measurements.
 */

let MapAdapter = null;

const PIN_SOURCE_ID = 'geometry-inventory-small-country-pins';
const PIN_LAYER_ID = 'geometry-inventory-small-country-symbols';
const PIN_HIT_LAYER_ID = 'geometry-inventory-small-country-hit';
const PIN_IMAGE_PREFIX = 'geometry-inventory-pin';
const PIN_FALLBACK_COLOR = '#6b7280';

/**
 * MapLibre symbol image for a small-country marker. Keep the fill tied to the
 * catalog-owned admin-depth ramp while the white keyline remains legible over
 * both land and water. Values come from the inventory payload, but validate
 * them before interpolating into SVG markup so malformed metadata cannot turn
 * into executable image content.
 */
function pinSvg(color) {
  const fill = /^#[0-9a-f]{6}$/i.test(String(color || ''))
    ? String(color)
    : PIN_FALLBACK_COLOR;
  return '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="34" viewBox="0 0 28 34">'
    + `<path fill="${fill}" stroke="#fff" stroke-width="2" d="M14 1C7.37 1 2 6.37 2 13c0 8.7 12 20 12 20s12-11.3 12-20C26 6.37 20.63 1 14 1Z"/>`
    + '<circle cx="14" cy="13" r="4" fill="#fff" fill-opacity=".92"/>'
    + '</svg>';
}

export function setDependencies(deps) {
  MapAdapter = deps.MapAdapter;
}

const MUTED = 'rgba(230, 243, 255, 0.62)';

// Lifecycle states collapse to the same five buckets the account-page family
// matrix uses, so one country reads identically in both surfaces.
const STATE_BUCKETS = {
  published: 'ready',
  runtime_qa: 'ready',
  graph_admitted: 'admitted',
  semantic_qa: 'qa',
  staged: 'qa',
  blocked_license: 'blocked',
  unavailable_machine_readable: 'blocked',
  not_applicable: 'neutral',
  upstream_empty: 'neutral'
};

const BUCKET_COLORS = {
  ready: '#37b24d',
  admitted: '#1c7ed6',
  qa: '#f2c037',
  blocked: '#e03131',
  neutral: '#6b7280',
  missing: '#4b5563'
};

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[char]));
}

function stateBucket(state) {
  return STATE_BUCKETS[String(state || '')] || 'missing';
}

/**
 * MapLibre serializes non-primitive feature properties to JSON text on the way
 * back out of a vector source, so the family list arrives as a string when it
 * comes from a map click and as an array when it comes straight from the
 * payload. Accept both rather than depending on which path called us.
 */
function readFamilyList(value) {
  if (Array.isArray(value)) return value;
  if (typeof value !== 'string' || !value.trim()) return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function chip(label, color) {
  return `<span class="gb-chip" style="border-color:${color};color:${color}">${escapeHtml(label)}</span>`;
}

function swatch(color) {
  return `<span class="gb-swatch" style="background:${color}"></span>`;
}

function fact(label, value) {
  return `<div class="gb-fact"><dt>${escapeHtml(label)}</dt><dd>${value}</dd></div>`;
}

export const GeometryPopup = {
  family: 'geometry_basics_popup',

  /**
   * Describe where a country's admin depth came from, in plain language.
   */
  depthProvenance(properties = {}) {
    switch (String(properties.coverage_basis || properties.depth_source || '')) {
      case 'enhanced_country_coverage':
      case 'country_program':
        return 'Enhanced country coverage available now.';
      case 'global_baseline':
      case 'shared_bank_baseline':
        return 'Available through the global geometry baseline.';
      default:
        return 'Currently available geometry coverage.';
    }
  },

  buildDepthLine(properties = {}) {
    const level = properties.max_admin_level;
    const color = properties.depth_color || BUCKET_COLORS.missing;
    if (level == null) {
      return `<div class="gb-depth">${swatch(color)}<span class="gb-depth-value">Admin depth unknown</span></div>`;
    }
    const tiers = Number(level);
    const detail = tiers === 0
      ? 'no subnational tiers'
      : `${tiers} subnational tier${tiers === 1 ? '' : 's'}`;
    return `<div class="gb-depth">${swatch(color)}`
      + `<span class="gb-depth-value">Admin ${escapeHtml(level)}</span>`
      + `<span class="gb-depth-detail">${detail}</span></div>`;
  },

  /**
   * Group the family list into available families and everything else, so a
   * deep spine beside an empty postal family reads honestly rather than
   * collapsing into one completion score.
   */
  buildFamilyContent(properties = {}) {
    const families = readFamilyList(properties.families);
    if (!families.length) return '';

    const available = families.filter((family) => family?.available);
    const internal = String(properties.catalog_view || '') === 'internal';
    const pending = internal ? families.filter((family) => {
      if (family?.available) return false;
      return String(family?.state || 'not_inventoried') !== 'not_inventoried';
    }) : [];
    const uninventoried = internal ? families.length - available.length - pending.length : 0;

    const group = (label, items, labeller) => items.length
      ? `<div class="gb-group"><div class="gb-group-label">${label}</div>`
        + `<div class="gb-chips">${items.map(labeller).join('')}</div></div>`
      : '';

    return group('Available', available, (family) => chip(
      family.short_label || family.label || family.family_id,
      BUCKET_COLORS[stateBucket(family.state)]
    ))
      + group('In progress or blocked', pending, (family) => chip(
        `${family.short_label || family.family_id}: ${family.state_label}`,
        BUCKET_COLORS[stateBucket(family.state)]
      ))
      + (uninventoried > 0
        ? `<div class="gb-note">${uninventoried} further famil${uninventoried === 1 ? 'y' : 'ies'} not inventoried</div>`
        : '');
  },

  /**
   * Full popup shown on click.
   */
  build(properties = {}) {
    const code = String(properties.loc_id || '').trim();
    const name = escapeHtml(properties.name || code || 'Unknown');
    const facts = [];
    if (properties.admin_authority) facts.push(fact('Authority', escapeHtml(properties.admin_authority)));
    if (properties.admin_baseline) facts.push(fact('Baseline', escapeHtml(properties.admin_baseline)));
    if (properties.admin_state_label) {
      facts.push(fact(
        'Spine',
        swatch(BUCKET_COLORS[stateBucket(properties.admin_state)]) + escapeHtml(properties.admin_state_label)
      ));
    }

    const footer = [];
    if (properties.inventory_as_of) footer.push(`Inventory as of ${escapeHtml(properties.inventory_as_of)}`);
    if (properties.coverage_matrix_status) footer.push(escapeHtml(properties.coverage_matrix_status));

    return '<div class="gb-popup">'
      + `<div class="gb-title">${name}${code ? `<span class="gb-code">${escapeHtml(code)}</span>` : ''}</div>`
      + this.buildDepthLine(properties)
      + `<div class="gb-note">${escapeHtml(this.depthProvenance(properties))}</div>`
      + (facts.length ? `<dl class="gb-facts">${facts.join('')}</dl>` : '')
      + this.buildFamilyContent(properties)
      + (footer.length ? `<div class="gb-foot">${footer.join('<br>')}</div>` : '')
      + '</div>';
  },

  /**
   * Hover shows the same content as a click: this popup is a status readout,
   * not a teaser, and holding detail back behind a click only makes an
   * operator click 250 countries to read the map.
   */
  buildHoverHtml(properties = {}) {
    return this.build(properties);
  },

  /**
   * Point features for the countries too small to see at world zoom. The
   * server decides which those are from real geodesic area and flags them
   * `is_small`, so the threshold lives with the measurement rather than in a
   * second list here that could drift away from it.
   */
  pinGeojson(geojson) {
    const features = [];
    for (const feature of geojson?.features || []) {
      const props = feature?.properties || {};
      if (!props.is_small) continue;
      const lon = Number(props.centroid_lon);
      const lat = Number(props.centroid_lat);
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue;
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [lon, lat] },
        properties: props
      });
    }
    return { type: 'FeatureCollection', features };
  },

  async ensurePinImages(map, geojson) {
    const colors = new Map();
    for (const feature of geojson?.features || []) {
      const level = feature?.properties?.max_admin_level;
      const key = level == null ? 'unknown' : String(level);
      if (!colors.has(key)) colors.set(key, feature.properties.depth_color || PIN_FALLBACK_COLOR);
    }
    await Promise.all(Array.from(colors.entries()).map(([key, color]) => new Promise((resolve) => {
      const imageId = `${PIN_IMAGE_PREFIX}-${key}`;
      if (map.hasImage(imageId)) { resolve(); return; }
      const image = new Image(28, 34);
      image.onload = () => {
        if (!map.hasImage(imageId)) map.addImage(imageId, image, { pixelRatio: 2 });
        resolve();
      };
      image.onerror = () => resolve();
      image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(pinSvg(color))}`;
    })));
  },

  /**
   * Show or hide the small-country pins. Safe to call before any data exists.
   */
  async setPinsVisible(visible, geojson = null) {
    const map = MapAdapter?.map;
    if (!map) return false;

    if (!visible) {
      for (const layerId of [PIN_LAYER_ID, PIN_HIT_LAYER_ID]) {
        if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', 'none');
      }
      return false;
    }

    const pins = this.pinGeojson(geojson);
    if (!pins.features.length) return false;
    await this.ensurePinImages(map, pins);

    if (map.getSource(PIN_SOURCE_ID)) {
      map.getSource(PIN_SOURCE_ID).setData(pins);
    } else {
      map.addSource(PIN_SOURCE_ID, { type: 'geojson', data: pins });
    }

    if (!map.getLayer(PIN_LAYER_ID)) {
      map.addLayer({
        id: PIN_LAYER_ID,
        type: 'symbol',
        source: PIN_SOURCE_ID,
        layout: {
          'icon-image': [
            'concat',
            `${PIN_IMAGE_PREFIX}-`,
            ['case', ['has', 'max_admin_level'], ['to-string', ['get', 'max_admin_level']], 'unknown']
          ],
          'icon-anchor': 'bottom',
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
          'icon-size': ['interpolate', ['linear'], ['zoom'], 0, 1, 3, 1.5, 6, 2]
        }
      });
    }

    if (!map.getLayer(PIN_HIT_LAYER_ID)) {
      map.addLayer({
        id: PIN_HIT_LAYER_ID,
        type: 'circle',
        source: PIN_SOURCE_ID,
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 0, 11, 3, 15, 6, 20],
          'circle-color': '#000000',
          'circle-opacity': 0,
          'circle-translate': [0, -9]
        }
      });
      map.on('mousemove', PIN_HIT_LAYER_ID, (event) => {
        map.getCanvas().style.cursor = 'pointer';
        const feature = event.features?.[0];
        if (!feature || MapAdapter.popupLocked) return;
        MapAdapter.showPopup([event.lngLat.lng, event.lngLat.lat], this.build(feature.properties));
      });
      map.on('mouseleave', PIN_HIT_LAYER_ID, () => {
        map.getCanvas().style.cursor = '';
        if (!MapAdapter.popupLocked) MapAdapter.hidePopup();
      });
      map.on('click', PIN_HIT_LAYER_ID, (event) => {
        const feature = event.features?.[0];
        if (feature) this.show([event.lngLat.lng, event.lngLat.lat], feature.properties);
      });
    }

    for (const layerId of [PIN_LAYER_ID, PIN_HIT_LAYER_ID]) {
      map.setLayoutProperty(layerId, 'visibility', 'visible');
    }
    return true;
  },

  removePins() {
    const map = MapAdapter?.map;
    if (!map) return;
    for (const layerId of [PIN_HIT_LAYER_ID, PIN_LAYER_ID]) {
      if (map.getLayer(layerId)) map.removeLayer(layerId);
    }
    if (map.getSource(PIN_SOURCE_ID)) map.removeSource(PIN_SOURCE_ID);
  },

  show(lngLat, properties = {}) {
    const html = this.build(properties);
    if (!MapAdapter) return;
    MapAdapter.registerFeaturePopupClick?.();
    MapAdapter.showPopup(lngLat, html);
    MapAdapter.popupLocked = true;
    MapAdapter.setSelectedPopupContext?.({
      kind: 'geometry',
      popupFamily: this.family,
      properties
    });
  }
};

export default GeometryPopup;
