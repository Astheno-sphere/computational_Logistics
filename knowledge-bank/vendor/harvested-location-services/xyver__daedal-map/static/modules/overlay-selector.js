/**
 * Overlay Selector - UI component for toggling data overlays.
 * Displays in top right, below zoom level and breadcrumbs.
 * Supports hierarchical categories with group toggle.
 *
 * Categories are loaded dynamically from /api/catalog/overlays.
 */

import { CONFIG } from './config.js';
import { fetchMsgpack } from './utils/fetch.js';
import { getCurrentProfile } from './auth.js';
import { getExploreDefaultOverlayIds } from './explore/default-overlays.js';
import { getResearchDefaultOverlayIds } from './research/default-overlays.js';
import { getOpsDefaultOverlayIds, getOpsPublicDefaultOverlayIds } from './ops/default-overlays.js';
import { setSourceVersion } from './overlay-cache.js';

// Legacy compatibility map. New Explore sources select a renderer through the
// authored display_contract carried by /api/catalog/overlays.
const DATA_TYPE_TO_MODEL = {
  'events': 'point-radius',
  'metrics': 'choropleth',
  'gridded': 'weather-grid',
  'geometry': 'polygon',
  'tract_status': 'choropleth'
};

const DISPLAY_FAMILY_TO_MODEL = {
  admin_choropleth: 'choropleth',
  geometry_overlay: 'polygon',
  navigation_geometry: 'polygon',
  point_collection: 'point-radius',
  building_overlay: 'polygon',
  raster_grid: 'weather-grid',
  raster_scene: 'ocean-raster'
};

const EVENT_RENDERING_MODEL_TO_MODEL = {
  point_radius_event: 'point-radius',
  geojson_first_event: 'point-radius',
  track_event: 'track',
  polygon_event: 'polygon'
};

function getDisplayContract(sources = []) {
  const contracts = sources
    .map((source) => source?.display_contract)
    .filter((contract) => contract && typeof contract === 'object');
  if (!contracts.length) return null;

  // An overlay may combine a yearly aggregate with its event source. The
  // event/raster/point renderer is the specific visual leaf; an aggregate is
  // an analytical companion, not a reason to downgrade it to choropleth.
  const priority = {
    event_overlay: 5,
    raster_scene: 4,
    raster_grid: 4,
    point_collection: 3,
    geometry_overlay: 2,
    navigation_geometry: 2,
    admin_choropleth: 1
  };
  const eventRenderingPriority = {
    // A combined hazard overlay can contain a point-only reporting source and
    // a prepared GeoJSON event source. Prefer the richest authored display
    // variant instead of whichever source happened to be catalogued first.
    geojson_first_event: 4,
    track_event: 3,
    polygon_event: 2,
    point_radius_event: 1
  };
  return contracts.sort((left, right) => (
    ((priority[right.family] || 0) * 10 + (eventRenderingPriority[right.rendering_model] || 0)) -
    ((priority[left.family] || 0) * 10 + (eventRenderingPriority[left.rendering_model] || 0))
  ))[0];
}

function getOverlayModel(overlayId, sources = [], fallbackDataType = 'metrics') {
  const contract = getDisplayContract(sources);
  if (contract?.family === 'event_overlay') {
    return EVENT_RENDERING_MODEL_TO_MODEL[contract.rendering_model] || 'point-radius';
  }
  if (contract?.family && DISPLAY_FAMILY_TO_MODEL[contract.family]) {
    return DISPLAY_FAMILY_TO_MODEL[contract.family];
  }
  return MODEL_OVERRIDES[overlayId] || DATA_TYPE_TO_MODEL[fallbackDataType] || 'point-radius';
}

// Icon mapping for overlay types
const OVERLAY_ICONS = {
  'admin_layers': 'A',
  'geometry_inventory': 'G',
  'demographics': 'D',
  'disasters': '!',
  'climate': 'C',
  'ocean_sst': 'O',
  'ocean-sst-grid': 'O',
  'usa': 'U',
  'earthquakes': 'E',
  'volcanoes': 'V',
  'hurricanes': 'H',
  'hurricanes_live': 'H',
  'tornadoes': 'R',
  'tsunamis': 'T',
  'wildfires': 'W',
  'floods': 'F',
  'cyclones': 'C',
  'landslides': 'L',
  'drought': 'D',
  'risk': 'R',
  'nri': 'N',
  'worldpop': 'P',
  'world_factbook': 'F',
  'un_wpp': 'U',
  'world_bank_wdi': 'W',
  'distributed_manufacturing': 'M',
  'cejst': 'C',
  'usa_industrial_activity': 'I',
  'usa_opportunity_zones': 'O',
  'storms': 'S',
  'fema': 'F',
  'desinventar': 'I',
  'reliefweb': 'R',
  'event_areas': 'A',
  'aurora': 'A',
  'nws_alerts': '!',
  'buoys': 'B'
};

// Compatibility overrides for operational or not-yet-migrated overlays only.
// Published Explore sources use their authored display_contract above.  Do not
// add a new source here: give it an explicit display contract instead.
const MODEL_OVERRIDES = {
  'hurricanes_live': 'track'
};

const OPS_FEED_TO_OVERLAY_IDS = {
  currency: ['currency'],
  cams_air_quality: ['cams-air-quality-grid'],
  earthquakes: ['earthquakes'],
  volcanoes: ['volcanoes'],
  hurricanes: ['hurricanes_live'],
  hurricanes_live: ['hurricanes_live'],
  ocean_sst: ['ocean-sst-grid'],
  era5_land_temperature: ['land-temperature-grid'],
  tsunamis: ['tsunamis'],
  // One logical feed combines the NIFC US and CWFIS Canada collectors.
  wildfires: ['wildfires'],
  noaa_aurora: ['aurora'],
  noaa_swpc: ['aurora'],
  usa_nws_alerts: ['nws_alerts'],
  noaa_ndbc: ['buoys'],
  weather: [
    'temperature',
    'humidity',
    'snow-depth',
    'precipitation',
    'cloud-cover',
    'pressure',
    'solar-radiation',
    'soil-temp',
    'soil-moisture'
  ]
};

function normalizeOpsFeedId(feedId) {
  const normalized = String(feedId || '').trim();
  if (normalized === 'hurricanes') return 'hurricanes_live';
  // Persisted profiles created before the composed North American wildfire
  // feed may still carry a physical collector id. Normalize before initial
  // tray/default-overlay calculation, not only after the watch API returns.
  if (normalized === 'wildfires_us_nifc' || normalized === 'wildfires_can_cwfis') return 'wildfires';
  return normalized;
}

const HIDDEN_CATALOG_OVERLAY_IDS = new Set([
  'ocean_sst',
]);

// Categories built dynamically from catalog
let ALL_CATEGORIES = [];
let CATEGORIES = [];
let ALL_OVERLAYS = [];
let VISIBLE_OVERLAYS = [];
// Pack-level default overrides (pack_id -> {default_load, default_question,
// default_response}) from /api/catalog/overlays. Override wins over source defaults.
let PACK_DEFAULTS = {};
// Source-level defaults (source_id -> {default_load, default_question,
// default_response}) for ?source= deep-links, including sources with no overlay.
let SOURCE_DEFAULTS = {};
let opsEffectiveFeeds = [];
let accountOverlayPolicyEnabled = true;
const laneShownAdjustments = new Map();

function deriveOverlaySourceIds(sources = []) {
  return Array.from(new Set(
    (Array.isArray(sources) ? sources : [])
      .map((source) => String(source?.source_id || '').trim())
      .filter(Boolean)
  ));
}

function deriveOverlayPackIds(overlayId, sources = []) {
  const packIds = new Set(
    (Array.isArray(sources) ? sources : [])
      .map((source) => String(source?.pack_id || '').trim())
      .filter(Boolean)
  );
  if (overlayId) {
    packIds.add(String(overlayId).trim());
  }
  return Array.from(packIds).filter(Boolean);
}

function normalizeFeedNames(values) {
  const out = [];
  for (const value of values || []) {
    const text = normalizeOpsFeedId(value);
    if (text && !out.includes(text)) {
      out.push(text);
    }
  }
  return out;
}

export function setOpsEffectiveFeeds(feeds = []) {
  opsEffectiveFeeds = normalizeFeedNames(feeds);
  OverlaySelector?.refreshVisibility?.();
  window.TickerController?.refreshVisibility?.();
}

export function hasExplicitOpsFeedSelection() {
  if (opsEffectiveFeeds.length > 0) {
    return true;
  }
  const profile = getCurrentProfile();
  return Array.isArray(profile?.ops_feeds) && profile.ops_feeds.length > 0;
}

function getAccountOpsFeedSelection(profile = getCurrentProfile()) {
  return normalizeFeedNames(
    Array.isArray(profile?.ops_feeds) ? profile.ops_feeds : []
  );
}

export function getOpsOverlayIdsForFeeds(feeds = []) {
  const overlayIds = new Set();
  for (const feed of feeds || []) {
    const ids = OPS_FEED_TO_OVERLAY_IDS[normalizeOpsFeedId(feed)] || [];
    for (const overlayId of ids) {
      overlayIds.add(overlayId);
    }
  }
  return Array.from(overlayIds);
}

export function getOpsFeedIdForOverlay(overlayId) {
  const normalizedOverlayId = String(overlayId || '').trim();
  if (!normalizedOverlayId) return '';
  if (normalizedOverlayId === 'hurricanes_live' || normalizedOverlayId === 'hurricanes') {
    return 'hurricanes_live';
  }
  for (const [feedId, overlayIds] of Object.entries(OPS_FEED_TO_OVERLAY_IDS)) {
    if (Array.isArray(overlayIds) && overlayIds.includes(normalizedOverlayId)) {
      return normalizeOpsFeedId(feedId);
    }
  }
  return '';
}

// Mode policy for the enable-zoom camera assist: only the Ops lane refits
// the camera when an overlay is toggled on in the tray. Explore can opt in
// here later.
function shouldAutoFocusOnOverlayEnable(mode) {
  return mode === 'ops';
}

// Grid/field overlays cover the planet rather than discrete events; enabling
// one means "show me the global picture", so they get a fixed world framing
// instead of a feature-bounds fit.
const GLOBAL_FOCUS_OVERLAY_IDS = new Set(['ocean-sst-grid', 'land-temperature-grid', 'cams-air-quality-grid', 'aurora']);

function focusGlobalOverlayView() {
  return Boolean(MapAdapter?.focusOnFeatures?.([
    { type: 'Feature', geometry: { type: 'Point', coordinates: [-170, -55] }, properties: {} },
    { type: 'Feature', geometry: { type: 'Point', coordinates: [170, 72] }, properties: {} }
  ]));
}

function getRenderedOpsGeojson(overlayId) {
  // Delegates to OverlayController: covers both inline ops snapshot payloads
  // (earthquakes-style) and endpoint-fetched dataCache features
  // (hurricanes-style track loads).
  const geojson = window.OverlayController?.getRenderedOverlayGeojson?.(overlayId);
  return Array.isArray(geojson?.features) && geojson.features.length ? geojson : null;
}

/**
 * Fit the camera to the union of every active Ops overlay's rendered
 * features. Returns false (no camera move) when nothing renderable is active.
 */
export function focusActiveOpsOverlays() {
  const collections = [];
  let hasActiveGlobalOverlay = false;
  for (const overlayId of OverlaySelector.getActiveOverlays()) {
    if (GLOBAL_FOCUS_OVERLAY_IDS.has(overlayId)) {
      hasActiveGlobalOverlay = true;
      continue;
    }
    const geojson = getRenderedOpsGeojson(overlayId);
    if (geojson) {
      collections.push(geojson);
    }
  }
  if (collections.length) {
    return Boolean(MapAdapter?.focusOnFeatures?.(collections));
  }
  // Only global grid/field overlays are active: world framing.
  if (hasActiveGlobalOverlay) {
    return focusGlobalOverlayView();
  }
  return false;
}

export function isOpsFeedAllowed(feedId) {
  const normalizedFeedId = normalizeOpsFeedId(feedId);
  if (!normalizedFeedId) return false;
  const overlayIds = getOpsOverlayIdsForFeeds([normalizedFeedId]);
  if (!overlayIds.length) return false;
  const allowedOverlayIds = getAllowedOpsOverlayIds();
  return overlayIds.some((overlayId) => allowedOverlayIds.has(overlayId));
}

export function getAllOpsManagedOverlayIds() {
  const overlayIds = new Set();
  for (const ids of Object.values(OPS_FEED_TO_OVERLAY_IDS)) {
    for (const overlayId of ids || []) {
      overlayIds.add(overlayId);
    }
  }
  return Array.from(overlayIds);
}

export function resolveOverlayIdFromSourceId(sourceId) {
  const normalizedSourceId = String(sourceId || '').trim();
  if (!normalizedSourceId) return '';
  const match = ALL_OVERLAYS.find((overlay) => Array.isArray(overlay?.sourceIds) && overlay.sourceIds.includes(normalizedSourceId));
  return match?.id || '';
}

export function resolveOverlayIdFromPackId(packId) {
  const normalizedPackId = String(packId || '').trim();
  if (!normalizedPackId) return '';
  const match = ALL_OVERLAYS.find((overlay) => Array.isArray(overlay?.packIds) && overlay.packIds.includes(normalizedPackId));
  return match?.id || '';
}

export function getOverlayCatalogEntryBySourceId(sourceId) {
  const normalizedSourceId = String(sourceId || '').trim();
  if (!normalizedSourceId) return null;
  for (const overlay of ALL_OVERLAYS) {
    const sources = Array.isArray(overlay?.sources) ? overlay.sources : [];
    const match = sources.find((source) => String(source?.source_id || '').trim() === normalizedSourceId);
    if (match) {
      return match;
    }
  }
  return null;
}

export function getOverlayCatalogEntriesByOverlayId(overlayId) {
  const normalizedOverlayId = String(overlayId || '').trim();
  if (!normalizedOverlayId) return [];
  const match = ALL_OVERLAYS.find((overlay) => String(overlay?.id || '').trim() === normalizedOverlayId);
  return Array.isArray(match?.sources) ? match.sources : [];
}

export function resolvePackIdFromSourceId(sourceId) {
  const normalizedSourceId = String(sourceId || '').trim();
  if (!normalizedSourceId) return '';
  const catalogEntry = getOverlayCatalogEntryBySourceId(normalizedSourceId);
  if (catalogEntry?.pack_id) {
    return String(catalogEntry.pack_id).trim();
  }
  const sourceDefault = getSourceDefaultOverride(normalizedSourceId);
  if (sourceDefault?.pack_id) {
    return String(sourceDefault.pack_id).trim();
  }
  return '';
}

export function getOverlayCatalogEntriesByPackId(packId) {
  const normalizedPackId = String(packId || '').trim();
  if (!normalizedPackId) return [];
  const matches = [];
  for (const overlay of ALL_OVERLAYS) {
    const sources = Array.isArray(overlay?.sources) ? overlay.sources : [];
    for (const source of sources) {
      if (String(source?.pack_id || '').trim() === normalizedPackId) {
        matches.push(source);
      }
    }
  }
  return matches;
}

// Pack-level default override authored in the pack metadata.json. Returns
// { default_load, default_question, default_response } or null.
export function getPackDefaultOverride(packId) {
  const normalizedPackId = String(packId || '').trim();
  if (!normalizedPackId) return null;
  return PACK_DEFAULTS[normalizedPackId] || null;
}

// Source-level default. Reachable even for sources with no overlay slot (e.g.
// metrics aggregates), unlike getOverlayCatalogEntryBySourceId. Returns
// { default_load, default_question, default_response } or null.
export function getSourceDefaultOverride(sourceId) {
  const normalizedSourceId = String(sourceId || '').trim();
  if (!normalizedSourceId) return null;
  return SOURCE_DEFAULTS[normalizedSourceId] || null;
}

function getDefaultOverlayIdsForMode(mode) {
  if (mode === 'explore') return [...getExploreDefaultOverlayIds()];
  if (mode === 'research') return [...getResearchDefaultOverlayIds()];
  if (mode === 'ops') return [...getOpsDefaultOverlayIds()];
  return [];
}

function getProfileLaneOverlayDefaults(profile, fieldName, mode) {
  const byLane = profile?.[fieldName];
  if (!byLane || typeof byLane !== 'object') return [];
  const values = Array.isArray(byLane[mode]) ? byLane[mode] : [];
  return values.map((item) => String(item || '').trim()).filter(Boolean);
}

function getBaseShownOverlayIdsForMode(mode = getCurrentOverlayLaneMode()) {
  const normalizedMode = String(mode || getCurrentOverlayLaneMode()).trim().toLowerCase() || 'explore';
  const profile = getCurrentProfile();
  const accountShown = accountOverlayPolicyEnabled
    ? getProfileLaneOverlayDefaults(profile, 'default_shown_by_lane', normalizedMode)
    : [];
  const accountOpsFeeds = accountOverlayPolicyEnabled
    ? getAccountOpsFeedSelection(profile)
    : [];
  // Keep the two Ops lanes distinct. Anonymous/default-watch visitors see the
  // curated public default set. An account with saved ops_feeds sees every
  // feed it selected, even when an older tray-layout preference lists fewer.
  if (normalizedMode === 'ops' && accountOpsFeeds.length) {
    return Array.from(new Set([
      ...getOpsOverlayIdsForFeeds(accountOpsFeeds),
      ...accountShown
    ]));
  }
  if (accountShown.length) {
    return accountShown;
  }
  return getDefaultOverlayIdsForMode(normalizedMode);
}

function getBaseEnabledOverlayIdsForMode(mode = getCurrentOverlayLaneMode()) {
  const normalizedMode = String(mode || getCurrentOverlayLaneMode()).trim().toLowerCase() || 'explore';
  const profile = getCurrentProfile();
  const accountEnabled = accountOverlayPolicyEnabled
    ? getProfileLaneOverlayDefaults(profile, 'default_enabled_by_lane', normalizedMode)
    : [];
  if (accountEnabled.length) {
    return accountEnabled;
  }
  return [];
}

function getVisibleTrayOverlayIdsForMode(mode = getCurrentOverlayLaneMode()) {
  const visible = new Set(getBaseShownOverlayIdsForMode(mode));
  const shownAdjustments = getShownAdjustmentsForMode(mode);
  for (const overlayId of shownAdjustments) {
    visible.add(overlayId);
  }
  if (OverlaySelector?.currentLaneMode === mode) {
    for (const overlayId of OverlaySelector.getActiveOverlays()) {
      visible.add(overlayId);
    }
  } else {
    const savedIds = OverlaySelector?.laneOverlayStates?.get?.(mode);
    if (Array.isArray(savedIds)) {
      for (const overlayId of savedIds) {
        visible.add(overlayId);
      }
    }
  }
  return visible;
}

function getCategoryDisplayLabel(category) {
  if (!category) return '';
  const laneMode = getCurrentOverlayLaneMode();
  if (laneMode === 'ops') {
    if (category.id === 'global_indicators') return 'Global';
    if (category.id === 'us_context') return 'USA';
  }
  if (category.id === 'global_indicators') return 'Global Indicators';
  if (category.id === 'us_context') return 'US Context';
  return category.label || '';
}

function buildAdminLayersOverlay() {
  return {
    id: 'admin_layers',
    label: 'Admin Layers',
    description: 'Canonical administrative geometry spine',
    default: false,
    locked: false,
    model: 'admin-layers',
    icon: 'A',
    hasYearFilter: false,
    alwaysVisible: true
  };
}

function buildGeometryInventoryOverlay() {
  return {
    id: 'geometry_inventory',
    label: 'Geometry Catalog',
    description: 'Explore currently available geometry depth by country',
    default: false,
    locked: false,
    model: 'polygon',
    icon: 'G',
    hasYearFilter: false,
    alwaysVisible: true
  };
}

function pushGeometryInventoryCategory(categories) {
  if (!Array.isArray(categories)) return;
  if (categories.some((category) => category?.id === 'geometry_inventory')) return;
  categories.push({
    id: 'geometry_inventory',
    label: 'Geometry Catalog',
    icon: 'G',
    isCategory: false,
    overlay: buildGeometryInventoryOverlay()
  });
}

function pushOverlayIfMissing(overlays, overlay) {
  if (!overlay?.id || !Array.isArray(overlays)) return;
  if (!overlays.some((candidate) => candidate?.id === overlay.id)) {
    overlays.push(overlay);
  }
}

/**
 * Build CATEGORIES from overlay_tree fetched from API.
 * @param {Object} overlayTree - The overlay_tree from catalog
 */
function buildCategoriesFromTree(overlayTree) {
  const categories = [{
    id: 'admin_layers',
    label: 'Admin Layers',
    icon: 'A',
    isCategory: false,
    overlay: buildAdminLayersOverlay()
  }];
  const globalIndicatorOverlays = [];
  const usContextOverlays = [];

  for (const [categoryId, categoryData] of Object.entries(overlayTree)) {
    const icon = OVERLAY_ICONS[categoryId] || categoryId[0].toUpperCase();

    // Check if this is a category with children or a standalone overlay
    if (categoryData.children) {
      // Category with sub-overlays (like disasters)
      const overlays = [];
      let allChildrenAreChoropleths = true;

      for (const [overlayId, overlayData] of Object.entries(categoryData.children)) {
        if (HIDDEN_CATALOG_OVERLAY_IDS.has(overlayId)) {
          continue;
        }
        // Get data_type from first source
        const firstSource = overlayData.sources?.[0];
        const dataType = firstSource?.data_type || 'events';
        const displayContract = getDisplayContract(overlayData.sources);
        const model = getOverlayModel(overlayId, overlayData.sources, dataType);
        if (model !== 'choropleth') {
          allChildrenAreChoropleths = false;
        }

        const overlay = {
          id: overlayId,
          label: overlayData.label || overlayId.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
          description: `${overlayData.sources?.length || 0} source(s)`,
          default: false,
          locked: false,
          model: model,
          displayContract,
          icon: OVERLAY_ICONS[overlayId] || overlayId[0].toUpperCase(),
          hasYearFilter: dataType === 'events',
          sources: overlayData.sources || [],
          sourceIds: deriveOverlaySourceIds(overlayData.sources),
          packIds: deriveOverlayPackIds(overlayId, overlayData.sources)
        };

        if (overlayId === 'risk' || (categoryId === 'climate' && overlayId.startsWith('fairfax_'))) {
          usContextOverlays.push(overlay);
          continue;
        }

        overlays.push(overlay);
      }

      // A choropleth is not necessarily global.  In particular FEMA is a
      // USA-scoped county layer authored under us_context; do not promote it
      // merely because every child happens to use the choropleth model.
      if ((categoryId === 'global_indicators' || allChildrenAreChoropleths) &&
          overlays.length && categoryId !== 'climate' && categoryId !== 'us_context') {
        globalIndicatorOverlays.push(...overlays);
        continue;
      }
      if (!overlays.length) {
        continue;
      }

      categories.push({
        id: categoryId,
        label: categoryData.label || categoryId.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
        icon: icon,
        isCategory: true,
        expanded: categoryId === 'disasters',  // Disasters expanded by default
        overlays: overlays
      });
    } else if (categoryData.sources) {
      // Standalone overlay (like demographics)
      if (HIDDEN_CATALOG_OVERLAY_IDS.has(categoryId)) {
        continue;
      }
      const firstSource = categoryData.sources?.[0];
      const dataType = firstSource?.data_type || 'metrics';
      const displayContract = getDisplayContract(categoryData.sources);
      const model = getOverlayModel(categoryId, categoryData.sources, dataType);

      const overlay = {
        id: categoryId,
        label: categoryData.label || categoryId.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
        description: `${categoryData.sources?.length || 0} source(s)`,
        default: false,
        locked: false,
        model: model,
        displayContract,
        icon: OVERLAY_ICONS[categoryId] || categoryId[0].toUpperCase(),
        hasYearFilter: dataType === 'events',
        sources: categoryData.sources || [],
        sourceIds: deriveOverlaySourceIds(categoryData.sources),
        packIds: deriveOverlayPackIds(categoryId, categoryData.sources)
      };

      if (model === 'choropleth' && categoryId !== 'us_context') {
        globalIndicatorOverlays.push(overlay);
        continue;
      }

      categories.push({
        id: categoryId,
        label: categoryData.label || categoryId.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
        icon: icon,
        isCategory: false,
        overlay
      });
    }
  }

  const historicalDisasterOverlays = [
    { id: 'earthquakes', label: 'Earthquakes', description: 'Historical seismic events', default: false, locked: false, model: 'point-radius', icon: 'E', hasYearFilter: true, sourceIds: ['earthquakes'], packIds: ['earthquakes'] },
    { id: 'hurricanes', label: 'Hurricanes', description: 'Historical storm tracks', default: false, locked: false, model: 'track', icon: 'H', hasYearFilter: true, sourceIds: ['hurricanes'], packIds: ['hurricanes'] },
    { id: 'volcanoes', label: 'Volcanoes', description: 'Historical volcanic eruptions', default: false, locked: false, model: 'point-radius', icon: 'V', hasYearFilter: true, sourceIds: ['volcanoes'], packIds: ['volcanoes'] },
    { id: 'wildfires', label: 'Wildfires', description: 'Historical wildfire events', default: false, locked: false, model: 'point-radius', icon: 'W', hasYearFilter: true, sourceIds: ['wildfires'], packIds: ['wildfires'] },
    { id: 'tsunamis', label: 'Tsunamis', description: 'Historical tsunami events', default: false, locked: false, model: 'point-radius', icon: 'T', hasYearFilter: true, sourceIds: ['tsunamis'], packIds: ['tsunamis'] },
    { id: 'tornadoes', label: 'Tornadoes', description: 'Historical tornado events', default: false, locked: false, model: 'point-radius', icon: 'T', hasYearFilter: true, sourceIds: ['tornadoes'], packIds: ['tornadoes'] },
    { id: 'floods', label: 'Floods', description: 'Historical flood events', default: false, locked: false, model: 'point-radius', icon: 'F', hasYearFilter: true, sourceIds: ['floods'], packIds: ['floods'] }
  ];
  const laneMode = getCurrentOverlayLaneMode();
  const disastersCategory = categories.find((cat) => cat.id === 'disasters' && cat.isCategory);
  if (laneMode !== 'ops') {
    if (disastersCategory?.overlays) {
      const existingIds = new Set(disastersCategory.overlays.map((overlay) => overlay.id));
      for (const overlay of historicalDisasterOverlays) {
        if (!existingIds.has(overlay.id)) {
          disastersCategory.overlays.push(overlay);
        }
      }
    } else {
      categories.push({
        id: 'disasters',
        label: 'Disasters',
        icon: '!',
        isCategory: true,
        expanded: true,
        overlays: historicalDisasterOverlays
      });
    }
  }

  // Ops uses a separate live hurricane overlay id so it cannot collide with
  // the historical IBTrACS hurricane overlay/cache used in Explore.
  const liveHurricaneOverlay = {
    id: 'hurricanes_live',
    label: 'Hurricanes',
    description: 'Live storm tracks and forecasts',
    default: false,
    locked: false,
    model: 'track',
    icon: 'H',
    hasYearFilter: false,
    live: true,
    sourceIds: ['hurricanes_live'],
    packIds: ['hurricanes']
  };
  const activeDisastersCategory = categories.find((cat) => cat.id === 'disasters' && cat.isCategory);
  if (activeDisastersCategory) {
    if (!activeDisastersCategory.overlays.some((overlay) => overlay.id === 'hurricanes_live')) {
      activeDisastersCategory.overlays.push(liveHurricaneOverlay);
    }
  } else {
    categories.push({
      id: 'disasters',
      label: 'Disasters',
      icon: '!',
      isCategory: true,
      expanded: true,
      overlays: [liveHurricaneOverlay]
    });
  }

  // The published catalog intentionally does not send anonymous visitors its
  // historical pack sources.  Ops must nevertheless expose the real, public
  // collector-backed hazard overlays.  Define those leaves here instead of
  // borrowing Explore catalog entries: the controller hydrates them from the
  // active Ops watch and its short retained-history window.
  if (getCurrentOverlayLaneMode() === 'ops') {
    const opsDisasters = categories.find((cat) => cat.id === 'disasters' && cat.isCategory);
    const opsLiveHazardOverlays = [
      { id: 'earthquakes', label: 'Earthquakes', description: 'Recent seismic events', default: false, locked: false, model: 'point-radius', icon: 'E', hasYearFilter: false, live: true },
      { id: 'wildfires', label: 'Wildfires', description: 'Current wildfire incidents', default: false, locked: false, model: 'point-radius', icon: 'W', hasYearFilter: false, live: true },
      { id: 'tsunamis', label: 'Tsunamis', description: 'Recent tsunami events', default: false, locked: false, model: 'point-radius', icon: 'T', hasYearFilter: false, live: true },
      { id: 'volcanoes', label: 'Volcanoes', description: 'Recent volcanic activity', default: false, locked: false, model: 'point-radius', icon: 'V', hasYearFilter: false, live: true }
    ];
    if (opsDisasters?.overlays) {
      const existingIds = new Set(opsDisasters.overlays.map((overlay) => overlay.id));
      for (const overlay of opsLiveHazardOverlays) {
        if (!existingIds.has(overlay.id)) {
          opsDisasters.overlays.push(overlay);
        }
      }
    }
  }

  // Add or extend climate overlays. Some catalogs now provide a Climate
  // category, so merge instead of blindly appending a duplicate section.
  const hardcodedClimateOverlays = [
    { id: 'aurora', label: 'Aurora', description: 'Live aurora conditions', default: false, locked: false, model: 'aurora', icon: 'A', hasYearFilter: false, live: true },
    { id: 'buoys', label: 'Ocean Buoys', description: 'Live NDBC buoy readings (sea temp, wind, waves)', default: false, locked: false, model: 'buoys', icon: 'B', hasYearFilter: false, live: true },
    {
      id: 'ocean-sst-grid',
      label: 'Ocean Temp Grid',
      description: 'Ocean temperature grid',
      default: false,
      locked: false,
      model: 'ocean-raster',
      icon: 'O',
      hasYearFilter: false,
      live: false,
      rasterSource: 'ocean_sst',
      // Two linked scenes of the same ocean_sst pack, like weather's hourly/
      // weekly/monthly tiers: "recent" is the smooth weekly-cadence animation
      // (2025-07-01+, preloaded on enable); "history" is the full 1982-2026
      // monthly archive, fetched on demand when the playhead leaves the
      // loaded range. The tiers merge into one continuous timeline and the
      // model renders the finest cadence covering each moment.
      rasterBasins: ['OCEAN_WEEKLY_1DEG_20250701'],
      rasterBasinsByLane: {
        explore: ['OCEAN_WEEKLY_1DEG_20250701'],
        research: ['OCEAN_WEEKLY_1DEG_20250701'],
        ops: ['OCEAN_LATEST']
      },
      rasterCadence: 'weekly',
      rasterCadenceByLane: {
        explore: 'weekly',
        research: 'weekly',
        ops: 'daily'
      },
      rasterHistoryBasins: ['OCEAN'],
      rasterHistoryBasinsByLane: {
        explore: ['OCEAN'],
        research: ['OCEAN']
      },
      rasterHistoryCadence: 'monthly',
      rasterHistoryCadenceByLane: {
        explore: 'monthly',
        research: 'monthly'
      },
      // Explore and Research are historical-analysis surfaces. Load the
      // monthly archive alongside the recent weekly scene so playback starts
      // with the complete 1982-present timeline rather than requiring a
      // preliminary manual scrub into the archive.
      rasterPreloadHistory: true,
      rasterVariable: 'sst_c'
    },
    {
      id: 'land-temperature-grid',
      label: 'Air Temperature',
      description: 'Monthly ERA5 2 m air temperature and anomaly',
      default: false,
      locked: false,
      model: 'ocean-raster',
      icon: 'T',
      hasYearFilter: false,
      live: false,
      rasterSource: 'era5_land_temperature',
      rasterBasins: ['LAND_TEMPERATURE'],
      rasterBasinsByLane: {
        explore: ['LAND_TEMPERATURE'],
        research: ['LAND_TEMPERATURE'],
        ops: ['LAND_TEMPERATURE_LATEST']
      },
      rasterCadence: 'monthly',
      rasterCadenceByLane: { explore: 'monthly', research: 'monthly', ops: 'monthly' },
      rasterHistoryBasins: ['LAND_TEMPERATURE'],
      rasterHistoryBasinsByLane: {
        explore: ['LAND_TEMPERATURE'],
        research: ['LAND_TEMPERATURE'],
        ops: ['LAND_TEMPERATURE_LATEST']
      },
      rasterHistoryCadence: 'monthly',
      rasterVariable: 'air_temperature_2m_c',
      // ERA5 2 m air temperature is a global atmospheric field. The panel
      // can optionally apply the shared physical land mask for land-only
      // analysis. Ops defaults to that land-only view; Explore and Research
      // retain the complete atmospheric field for comparison with SST.
      rasterMaskMode: 'none',
      rasterMaskModeByLane: { ops: 'land' }
    }
  ];
  const climateCategory = categories.find((cat) => cat.id === 'climate' && cat.isCategory);
  if (climateCategory) {
    const existingOverlayIds = new Set((climateCategory.overlays || []).map((overlay) => overlay.id));
    for (const overlay of hardcodedClimateOverlays) {
      if (!existingOverlayIds.has(overlay.id)) {
        climateCategory.overlays.push(overlay);
      }
    }
  } else {
    categories.push({
      id: 'climate',
      label: 'Climate',
      icon: 'C',
      isCategory: true,
      expanded: false,
      overlays: hardcodedClimateOverlays
    });
  }

  // Global indicator overlays - the shared choropleth (global.csv country fills, etc.).
  // Only published packs belong in this fallback list. Internal or draft packs
  // (currency, worldpop, distributed_manufacturing) reach the tray only through
  // the catalog overlay tree, so the WIP surface can still test them.
  const qaIndicatorOverlays = [
    { id: 'un_wpp', label: 'UN Population', description: 'UN World Population Prospects', icon: 'U', sourceIds: ['un_wpp'], packIds: ['un_wpp'] },
    { id: 'world_factbook', label: 'World Factbook', description: 'Country indicators from the World Factbook', icon: 'F', sourceIds: ['world_factbook', 'world_factbook_static'], packIds: ['world_factbook'] },
    { id: 'world_bank_wdi', label: 'World Bank WDI', description: 'World Development Indicators', icon: 'W', sourceIds: ['world_bank_wdi'], packIds: ['world_bank_wdi'] }
  ];
  for (const overlay of qaIndicatorOverlays) {
    pushOverlayIfMissing(globalIndicatorOverlays, {
      ...overlay,
      default: false,
      locked: false,
      model: 'choropleth',
      hasYearFilter: false
    });
  }

  const qaUsContextOverlays = [
    { id: 'nri', label: 'Natural Risk Index', description: 'FEMA natural hazard risk', icon: 'N', sourceIds: ['fema_nri'], packIds: ['nri'] },
    { id: 'cejst', label: 'CEJST', description: 'Climate and economic justice screening', icon: 'C', sourceIds: ['cejst_classification', 'cejst_burdens'], packIds: ['cejst'] },
    { id: 'usa_industrial_activity', label: 'Industrial Activity', description: 'US industrial activity indicators', icon: 'I', sourceIds: ['usa_industrial_activity'], packIds: ['usa_industrial_activity'] },
    { id: 'usa_opportunity_zones', label: 'Opportunity Zones', description: 'US opportunity zone status', icon: 'O', sourceIds: ['usa_opportunity_zones'], packIds: ['usa_opportunity_zones'] }
  ];
  for (const overlay of qaUsContextOverlays) {
    pushOverlayIfMissing(usContextOverlays, {
      ...overlay,
      default: false,
      locked: false,
      model: 'choropleth',
      hasYearFilter: false
    });
  }

  pushOverlayIfMissing(usContextOverlays, {
    id: 'risk',
    label: 'Risk',
    description: 'US hazard risk overlays',
    default: false,
    locked: false,
    model: 'choropleth',
    icon: 'R',
    hasYearFilter: false,
    sourceIds: ['fema_nri'],
    packIds: ['nri']
  });

  if (globalIndicatorOverlays.length) {
    categories.push({
      id: 'global_indicators',
      label: 'Global Indicators',
      icon: 'G',
      isCategory: true,
      expanded: false,
      overlays: globalIndicatorOverlays
    });
  }

  // US context overlays - US-only risk, alert, and local coverage surfaces.
  // NOTE: the announcement ticker is intentionally NOT here - it is a display
  // surface (chrome) that aggregates many feeds, not a single-feed overlay.
  categories.push({
    id: 'us_context',
    label: 'US Context',
    icon: 'U',
    isCategory: true,
    expanded: false,
    overlays: [
      ...usContextOverlays,
      { id: 'nws_alerts', label: 'US Weather Alerts', description: 'Live NWS warnings', default: false, locked: false, model: 'nws_alerts', icon: '!', hasYearFilter: false, live: true }
    ]
  });

  pushGeometryInventoryCategory(categories);

  return dedupeCategories(categories);
}

function dedupeCategories(categories) {
  const merged = new Map();

  for (const category of categories || []) {
    if (!category || !category.id) continue;

    if (!merged.has(category.id)) {
      if (category.isCategory) {
        merged.set(category.id, {
          ...category,
          overlays: [...(category.overlays || [])]
        });
      } else if (category.overlay) {
        merged.set(category.id, {
          ...category,
          overlay: { ...category.overlay }
        });
      } else {
        merged.set(category.id, { ...category });
      }
      continue;
    }

    const existing = merged.get(category.id);
    if (existing.isCategory && category.isCategory) {
      const seenOverlayIds = new Set((existing.overlays || []).map((overlay) => overlay.id));
      for (const overlay of category.overlays || []) {
        if (!seenOverlayIds.has(overlay.id)) {
          existing.overlays.push(overlay);
          seenOverlayIds.add(overlay.id);
        }
      }
      existing.label = existing.label || category.label;
      existing.icon = existing.icon || category.icon;
      existing.expanded = existing.expanded || category.expanded;
      continue;
    }

    if (!existing.isCategory && !category.isCategory && category.overlay && !existing.overlay) {
      existing.overlay = { ...category.overlay };
    }
  }

  return Array.from(merged.values());
}

/**
 * Flatten overlays for lookup.
 */
function getAllOverlaysFromCategories(categories) {
  const overlays = [];
  for (const cat of categories) {
    if (cat.isCategory) {
      overlays.push(...cat.overlays);
    } else if (cat.overlay) {
      overlays.push(cat.overlay);
    }
  }
  return overlays;
}

function getCurrentOverlayLaneMode() {
  if (document.body.classList.contains('chat-mode-ops')) return 'ops';
  if (document.body.classList.contains('chat-mode-research')) return 'research';
  return 'explore';
}

/**
 * Register per-source content versions (Task L5 activation) from the
 * overlay tree's per-source `data_version` field, so the coverage ledger's
 * invalidateVersion hook has a real signal instead of always-null. Registers
 * under BOTH keys the ledger is queried by: the leaf/overlay id (event
 * claims key by overlayId -- see buildEventRangeClaim call sites) and each
 * member source_id (metric claims key by sourceId -- see buildMetricClaim
 * call sites). Walks nested category children recursively.
 * @param {object} overlayTree
 */
function registerOverlayTreeVersions(overlayTree) {
  for (const [key, node] of Object.entries(overlayTree || {})) {
    if (!node || typeof node !== 'object') continue;
    if (node.children) {
      registerOverlayTreeVersions(node.children);
      continue;
    }
    if (Array.isArray(node.sources)) {
      let leafVersion = null;
      for (const source of node.sources) {
        const version = source && source.data_version;
        if (!version) continue;
        setSourceVersion(source.source_id, version);
        if (!leafVersion || String(version) > String(leafVersion)) {
          leafVersion = version;
        }
      }
      if (leafVersion) {
        setSourceVersion(key, leafVersion);
      }
    }
  }
}

export function applyOverlayCatalogResponse(response = {}) {
  const overlayTree = response.overlay_tree || {};
  PACK_DEFAULTS = response.pack_defaults || {};
  SOURCE_DEFAULTS = response.source_defaults || {};
  ALL_CATEGORIES = buildCategoriesFromTree(overlayTree);
  if (response.catalog_surface === 'wip') {
    // WIP is an explicitly authorized local/admin test surface.  Its draft
    // and can-share catalog sources must not be hidden behind the normal
    // curated Explore tray allowlist, or a valid WIP source cannot be tested
    // from the map at all.  Keep published sources on their usual curated
    // posture; reveal only the non-published leaves returned by this response.
    const wipSourceIds = new Set(
      (Array.isArray(response.sources) ? response.sources : [])
        .filter((source) => String(source?.release_state || '').trim().toLowerCase() !== 'published')
        .map((source) => String(source?.source_id || '').trim())
        .filter(Boolean)
    );
    const wipMode = getCurrentOverlayLaneMode();
    const wipShown = laneShownAdjustments.get(wipMode) || new Set();
    // These sources are useful WIP catalog fixtures but have no current-state
    // Ops contract. They must not be promoted into an Ops tray merely because
    // the local WIP catalog exposes their Explore data.
    const OPS_EXPLORE_ONLY_WIP_SOURCES = new Set([
      'epa_aqs',
      'fema_nri',
      'future_nri',
    ]);
    // These are either shared Explore rendering controls rather than data
    // products, or are static/reference products with no current-state Ops
    // contract.  Keep them testable in Explore/Research WIP, but never let a
    // broad WIP source response turn them into apparent live Ops feeds.
    const OPS_EXPLORE_ONLY_WIP_OVERLAYS = new Set([
      'admin_layers',
      'demographics',
      'geography',
      'zip_codes',
      'tribal_areas',
      'watersheds',
      'parks',
      'risk',
      'nri_risk',
    ]);
    if (wipSourceIds.size) {
      for (const overlay of getAllOverlaysFromCategories(ALL_CATEGORIES)) {
        const sourceIds = overlay.sourceIds || [];
        const isNriSource = sourceIds.some((sourceId) => sourceId.startsWith('nri_'));
        const isOpsExploreOnly = wipMode === 'ops' && (
          OPS_EXPLORE_ONLY_WIP_OVERLAYS.has(overlay.id)
          || isNriSource
          || (sourceIds.length > 0
            && sourceIds.every((sourceId) => OPS_EXPLORE_ONLY_WIP_SOURCES.has(sourceId)))
        );
        if (!isOpsExploreOnly && sourceIds.some((sourceId) => wipSourceIds.has(sourceId))) {
          wipShown.add(overlay.id);
        }
      }
      laneShownAdjustments.set(wipMode, wipShown);
    }
    if (wipSourceIds.has('cams_air_quality')) {
      const climate = ALL_CATEGORIES.find((category) => category.id === 'climate' && category.isCategory);
      if (climate?.overlays && !climate.overlays.some((overlay) => overlay.id === 'cams-air-quality-grid')) {
        climate.overlays.push({
          id: 'cams-air-quality-grid', label: 'CAMS PM2.5',
          description: 'Global modeled PM2.5: monthly reanalysis history plus recent forecast frames',
          default: false, locked: false, model: 'ocean-raster', icon: 'A', hasYearFilter: false,
          live: false, rasterSource: 'cams_air_quality', rasterBasins: ['CAMS_EAC4_MONTHLY_WIP', 'CAMS_PM25_WIP'],
          // Explore retains its historical stack. Ops reads the compact rolling
          // bundle of real daily lead-zero analysis frames only.
          rasterBasinsByLane: { explore: ['CAMS_EAC4_MONTHLY_WIP', 'CAMS_PM25_WIP'], research: ['CAMS_EAC4_MONTHLY_WIP', 'CAMS_PM25_WIP'], ops: ['CAMS_PM25_ANALYSIS_LATEST'] },
          rasterCadence: 'daily', rasterCadenceByLane: { explore: 'daily', research: 'daily', ops: 'twice_daily' },
          rasterVariable: 'pm25_ug_m3', rasterMaskMode: 'none', alwaysVisible: true
        });
      }
      // The injected CAMS test overlay is not part of the normal catalog
      // tree yet, so it was not present during the source-to-overlay loop
      // above. Add it explicitly before Ops applies its feed allow-list.
      wipShown.add('cams-air-quality-grid');
      laneShownAdjustments.set(wipMode, wipShown);
    }
    // AirNow/OpenAQ are Ops-only WIP feeds, not Explore/catalog sources. The
    // catalog may load before the body receives its final lane class on a
    // fresh visit, so register this adjustment explicitly for Ops rather than
    // depending on the transient lane active during response handling.
    const global = ALL_CATEGORIES.find((category) => (
      category.id === 'global' || category.id === 'global_indicators'
    ) && category.isCategory);
    if (global?.overlays && !global.overlays.some((overlay) => overlay.id === 'air_quality_stations')) {
      global.overlays.push({
        id: 'air_quality_stations', label: 'Air Quality Stations (WIP)',
        description: 'AirNow AQI reporting areas plus the private OpenAQ six-pollutant station index; source-native values',
        default: false, locked: false, model: 'air_quality_stations', icon: 'A', hasYearFilter: false,
        live: true, sourceIds: ['airnow', 'openaq'], packIds: []
      });
    }
    const opsWipShown = laneShownAdjustments.get('ops') || new Set();
    opsWipShown.add('air_quality_stations');
    laneShownAdjustments.set('ops', opsWipShown);
  }
  const catalogSourceIds = new Set(
    (Array.isArray(response.sources) ? response.sources : [])
      .map((source) => String(source?.source_id || '').trim())
      .filter(Boolean)
  );
  const usContext = ALL_CATEGORIES.find((category) => category.id === 'us_context');
  if (catalogSourceIds.has('nws_alerts_historical') && usContext?.overlays && !usContext.overlays.some((overlay) => overlay.id === 'nws_alerts_historical')) {
    usContext.overlays.push({ id: 'nws_alerts_historical', source_id: 'nws_alerts_historical', label: 'NWS Alerts', description: 'Historical alert playback', default: false, locked: false, model: 'nws_alerts', icon: '!', hasYearFilter: true, alwaysVisible: true });
  }
  // CAMS is an Ops-only public feed, not a normal data-catalog surface. Add
  // its tray definition directly in Ops so published catalog filtering can
  // never leak the source into Explore or Research.
  if (getCurrentOverlayLaneMode() === 'ops') {
    const climate = ALL_CATEGORIES.find((category) => category.id === 'climate' && category.isCategory);
    if (climate?.overlays && !climate.overlays.some((overlay) => overlay.id === 'cams-air-quality-grid')) {
      climate.overlays.push({
        id: 'cams-air-quality-grid', label: 'CAMS PM2.5',
        description: 'Global modeled surface PM2.5 analyses from CAMS; updated from real 00/12 UTC source cycles',
        default: false, locked: false, model: 'ocean-raster', icon: 'A', hasYearFilter: false,
        live: true, rasterSource: 'cams_air_quality', rasterBasins: ['CAMS_PM25_ANALYSIS_LATEST'],
        rasterBasinsByLane: { ops: ['CAMS_PM25_ANALYSIS_LATEST'] },
        rasterCadence: 'twice_daily', rasterCadenceByLane: { ops: 'twice_daily' },
        rasterVariable: 'pm25_ug_m3', rasterMaskMode: 'none', alwaysVisible: true,
      });
    }
  }
  CATEGORIES = filterCategoriesForCurrentMode(ALL_CATEGORIES);
  ALL_OVERLAYS = getAllOverlaysFromCategories(ALL_CATEGORIES);
  VISIBLE_OVERLAYS = getAllOverlaysFromCategories(CATEGORIES);
  registerOverlayTreeVersions(overlayTree);
}

export function getAllowedOpsOverlayIds() {
  const profile = getCurrentProfile();
  const profileFeeds = Array.isArray(profile?.ops_feeds) ? profile.ops_feeds : [];
  const opsFeeds = opsEffectiveFeeds.length ? opsEffectiveFeeds : profileFeeds;
  const shownAdjustments = getShownAdjustmentsForMode('ops');
  if (!opsFeeds.length) {
    return new Set([...getOpsPublicDefaultOverlayIds(), ...shownAdjustments]);
  }
  const allowed = new Set();
  for (const feed of opsFeeds) {
    const overlayIds = OPS_FEED_TO_OVERLAY_IDS[normalizeOpsFeedId(feed)] || [];
    for (const overlayId of overlayIds) {
      allowed.add(overlayId);
    }
  }
  for (const overlayId of shownAdjustments) {
    allowed.add(overlayId);
  }
  return allowed;
}

function getShownAdjustmentsForMode(mode = getCurrentOverlayLaneMode()) {
  return laneShownAdjustments.get(mode) || new Set();
}

export function getShownOverlayIdsForMode(mode = getCurrentOverlayLaneMode()) {
  const visible = Array.from(getVisibleTrayOverlayIdsForMode(mode));
  if (mode !== 'ops') {
    return visible;
  }
  const allowed = getAllowedOpsOverlayIds();
  return visible.filter((overlayId) => allowed.has(overlayId));
}

function cloneVisibleCategories(categories) {
  return categories.map((cat) => {
    if (cat.isCategory) {
      return {
        ...cat,
        overlays: [...cat.overlays]
      };
    }
    if (cat.overlay) {
      return {
        ...cat,
        overlay: { ...cat.overlay }
      };
    }
    return { ...cat };
  });
}

function filterCategoriesForCurrentMode(categories) {
  const cloned = cloneVisibleCategories(categories);
  const laneMode = getCurrentOverlayLaneMode();
  const visibleTrayOverlayIds = getVisibleTrayOverlayIdsForMode(laneMode);
  if (laneMode !== 'ops') {
    const visibleCategories = [];
    for (const category of cloned) {
      if (category.isCategory) {
        const overlays = category.overlays.filter((overlay) => overlay.alwaysVisible || visibleTrayOverlayIds.has(overlay.id));
        if (overlays.length) {
          visibleCategories.push({
            ...category,
            overlays
          });
        }
        continue;
      }
      if (category.overlay && (category.overlay.alwaysVisible || visibleTrayOverlayIds.has(category.overlay.id))) {
        visibleCategories.push(category);
      }
    }
    return visibleCategories;
  }

  const allowedOverlayIds = getAllowedOpsOverlayIds();

  const visibleCategories = [];
  for (const category of cloned) {
    if (category.isCategory) {
      const overlays = category.overlays.filter((overlay) => (overlay.alwaysVisible || visibleTrayOverlayIds.has(overlay.id)) && allowedOverlayIds.has(overlay.id));
      if (overlays.length) {
        visibleCategories.push({
          ...category,
          overlays
        });
      }
      continue;
    }

    if (category.overlay && visibleTrayOverlayIds.has(category.overlay.id) && allowedOverlayIds.has(category.overlay.id)) {
      visibleCategories.push(category);
    }
  }

  return visibleCategories;
}

// Dependencies (set via setDependencies)
let MapAdapter = null;
let ModelRegistry = null;

export function setDependencies(deps) {
  MapAdapter = deps.MapAdapter;
  ModelRegistry = deps.ModelRegistry;
}

export const OverlaySelector = {
  // State
  activeOverlays: new Set(),
  laneOverlayStates: new Map(),
  currentLaneMode: 'explore',
  expanded: true,  // Default expanded
  categoryExpanded: {},  // Track which categories are expanded
  initialized: false,

  // DOM elements
  container: null,
  header: null,
  list: null,

  // Change listeners
  listeners: [],

  applyLaneDefaults(mode = this.currentLaneMode) {
    const baseEnabled = getBaseEnabledOverlayIdsForMode(mode);
    this.laneOverlayStates.set(mode, [...baseEnabled]);
    if (mode === this.currentLaneMode) {
      this.activeOverlays.clear();
      for (const overlayId of baseEnabled) {
        this.activeOverlays.add(overlayId);
      }
      this._rememberCurrentLaneState();
    }
  },

  /**
   * Initialize the overlay selector UI.
   * Fetches categories from API and builds UI.
   */
  async init(options = {}) {
    const restoreState = options.restoreState !== false;
    accountOverlayPolicyEnabled = options.accountOverlayPolicy !== false;
    this.currentLaneMode = getCurrentOverlayLaneMode();
    // A catalog-surface change may remove a draft overlay that is currently
    // rendered. Preserve this set so the normal listener path can explicitly
    // clear it after the replacement catalog has loaded.
    const activeBeforeCatalogReload = new Set(this.activeOverlays);
    // Find container first
    this.container = document.getElementById('overlaySelector');
    if (!this.container) {
      console.warn('OverlaySelector: #overlaySelector not found in DOM');
      return;
    }

    // Show loading state
    this.container.innerHTML = '<div class="overlay-header"><span class="overlay-title">Loading overlays...</span></div>';

    try {
      // Fetch overlay tree from API
      const lane = this.currentLaneMode;
      const useWip = window.localStorage.getItem(`useWipCatalog:${lane}`) === '1';
      const response = await fetchMsgpack(`/api/catalog/overlays?catalog_surface=${useWip ? 'wip' : 'published'}&catalog_lane=${encodeURIComponent(lane)}`);
      applyOverlayCatalogResponse(response);

      console.log('OverlaySelector: Loaded', CATEGORIES.length, 'visible categories,', VISIBLE_OVERLAYS.length, 'visible overlays from catalog');
    } catch (err) {
      console.error('OverlaySelector: Failed to load from API, using fallback', err);
      // Fallback to minimal hardcoded categories
      ALL_CATEGORIES = [
        {
          id: 'admin_layers',
          label: 'Admin Layers',
          icon: 'A',
          isCategory: false,
          overlay: buildAdminLayersOverlay()
        },
        {
          id: 'global_indicators',
          label: 'Global Indicators',
          icon: 'G',
          isCategory: true,
          expanded: false,
          alwaysVisible: true,
          overlays: [
            { id: 'demographics', label: 'Demographics', description: 'Choropleth data', default: false, locked: false, model: 'choropleth', icon: 'D', hasYearFilter: false }
          ]
        },
        {
          id: 'disasters',
          label: 'Disasters',
          icon: '!',
          isCategory: true,
          expanded: true,
          overlays: [
            { id: 'earthquakes', label: 'Earthquakes', description: 'Seismic events', default: false, locked: false, model: 'point-radius', icon: 'E', hasYearFilter: true },
            { id: 'hurricanes', label: 'Hurricanes', description: 'Storm tracks', default: false, locked: false, model: 'track', icon: 'H', hasYearFilter: true },
            { id: 'hurricanes_live', label: 'Hurricanes', description: 'Live storm tracks and forecasts', default: false, locked: false, model: 'track', icon: 'H', hasYearFilter: false, live: true },
            { id: 'wildfires', label: 'Wildfires', description: 'Fire events', default: false, locked: false, model: 'point-radius', icon: 'W', hasYearFilter: true }
          ]
        }
      ];
      pushGeometryInventoryCategory(ALL_CATEGORIES);
      CATEGORIES = filterCategoriesForCurrentMode(ALL_CATEGORIES);
      ALL_OVERLAYS = getAllOverlaysFromCategories(ALL_CATEGORIES);
      VISIBLE_OVERLAYS = getAllOverlaysFromCategories(CATEGORIES);
    }

    // Restore only in-memory lane state from the current runtime session.
    // Persistent browser restore is intentionally disabled; defaults or URL/
    // account-backed state should be authoritative on a fresh visit.
    if (restoreState && !this._restoreState(this.currentLaneMode)) {
      this.applyLaneDefaults(this.currentLaneMode);
    } else if (!restoreState) {
      this.activeOverlays.clear();
      this.applyLaneDefaults(this.currentLaneMode);
    }

    // Switching WIP off must remove its active map layers, not merely hide the
    // checkbox. This is especially important in Ops, where a retained live or
    // raster overlay could otherwise look like public runtime state. The same
    // cleanup applies to every lane because catalog surface is shared locally.
    const visibleOverlayIds = new Set(VISIBLE_OVERLAYS.map((overlay) => overlay.id));
    const removedByCatalogSurface = [];
    for (const overlayId of activeBeforeCatalogReload) {
      if (!visibleOverlayIds.has(overlayId) && this.activeOverlays.has(overlayId)) {
        this.activeOverlays.delete(overlayId);
        removedByCatalogSurface.push(overlayId);
      }
    }
    this._rememberCurrentLaneState();

    // Initialize category expanded state
    for (const cat of CATEGORIES) {
      if (cat.isCategory) {
        this.categoryExpanded[cat.id] = cat.expanded || false;
      }
    }

    // Build UI
    this._buildUI();

    // Wire up events
    this._setupEvents();

    this.initialized = true;
    for (const overlayId of removedByCatalogSurface) {
      this._notifyListeners(overlayId, false, {
        suppressStatusMessage: true,
        systemTransition: true
      });
    }
    console.log('OverlaySelector initialized with:', Array.from(this.activeOverlays));
  },

  /**
   * Build the overlay selector UI elements.
   * @private
   */
  _buildUI() {
    this.container.innerHTML = '';

    // Header (clickable to expand/collapse)
    this.header = document.createElement('div');
    this.header.className = 'overlay-header';
    const modeLabel = this.currentLaneMode === 'ops'
      ? 'Ops Overlays'
      : this.currentLaneMode === 'research'
        ? 'Research Overlays'
        : 'Explore Overlays';
    this.header.innerHTML = `
      <span class="overlay-title">${modeLabel}</span>
      <span class="overlay-toggle">${this.expanded ? '-' : '+'}</span>
    `;
    this.container.appendChild(this.header);

    // List container
    this.list = document.createElement('div');
    this.list.className = 'overlay-list';
    this.list.style.display = this.expanded ? 'block' : 'none';

    // Build categories and overlays
    for (const cat of CATEGORIES) {
      if (cat.isCategory) {
        // Category with sub-items
        const categoryEl = this._createCategory(cat);
        this.list.appendChild(categoryEl);
      } else if (cat.overlay) {
        // Standalone overlay (like Demographics)
        const item = this._createOverlayItem(cat.overlay, false);
        this.list.appendChild(item);
      }
    }

    this.container.appendChild(this.list);
  },

  /**
   * Create a category element with sub-overlays.
   * @private
   */
  _createCategory(category) {
    const wrapper = document.createElement('div');
    wrapper.className = 'overlay-category';
    wrapper.dataset.categoryId = category.id;

    // Check if any overlays in this category are active
    const activeCount = category.overlays.filter(o => this.activeOverlays.has(o.id)).length;
    const allActive = activeCount === category.overlays.length;
    const someActive = activeCount > 0 && !allActive;

    // Category header
    const header = document.createElement('div');
    header.className = 'overlay-category-header';
    header.innerHTML = `
      <input type="checkbox"
             class="category-checkbox"
             data-category-id="${category.id}"
             ${allActive ? 'checked' : ''}
             ${someActive ? 'data-indeterminate="true"' : ''}>
      <span class="overlay-icon">${category.icon}</span>
      <span class="overlay-label">${getCategoryDisplayLabel(category)}</span>
      <span class="category-toggle">${this.categoryExpanded[category.id] ? '-' : '+'}</span>
    `;
    wrapper.appendChild(header);

    // Set indeterminate state after adding to DOM
    setTimeout(() => {
      const checkbox = header.querySelector('.category-checkbox');
      if (checkbox && someActive) {
        checkbox.indeterminate = true;
      }
    }, 0);

    // Sub-overlay list
    const subList = document.createElement('div');
    subList.className = 'overlay-sub-list';
    subList.style.display = this.categoryExpanded[category.id] ? 'block' : 'none';

    for (const overlay of category.overlays) {
      const item = this._createOverlayItem(overlay, true);
      subList.appendChild(item);
    }

    wrapper.appendChild(subList);
    return wrapper;
  },

  /**
   * Create a single overlay item element.
   * @private
   */
  _createOverlayItem(overlay, isSubItem = false) {
    const item = document.createElement('label');
    item.className = 'overlay-item' + (isSubItem ? ' overlay-sub-item' : '');
    item.dataset.overlayId = overlay.id;

    const isChecked = this.activeOverlays.has(overlay.id);
    const isLocked = overlay.locked;
    const isPlaceholder = overlay.placeholder;

    item.innerHTML = `
      <input type="checkbox"
             ${isChecked ? 'checked' : ''}
             ${isLocked ? 'disabled' : ''}
             ${isPlaceholder ? 'disabled' : ''}
             data-overlay-id="${overlay.id}">
      <span class="overlay-icon">${overlay.icon || overlay.id[0].toUpperCase()}</span>
      <span class="overlay-label ${isPlaceholder ? 'placeholder' : ''}">${overlay.label}${isPlaceholder ? ' (soon)' : ''}</span>
    `;

    return item;
  },

  /**
   * Set up event handlers.
   * @private
   */
  _setupEvents() {
    // Header click - expand/collapse main list
    this.header.addEventListener('click', () => {
      this.expanded = !this.expanded;
      this.list.style.display = this.expanded ? 'block' : 'none';
      this.header.querySelector('.overlay-toggle').textContent = this.expanded ? '-' : '+';
    });

    // Category header clicks - expand/collapse sub-list and toggle all
    this.list.addEventListener('click', (e) => {
      const categoryHeader = e.target.closest('.overlay-category-header');
      if (!categoryHeader) return;

      const wrapper = categoryHeader.closest('.overlay-category');
      const categoryId = wrapper.dataset.categoryId;
      const checkbox = categoryHeader.querySelector('.category-checkbox');

      // If clicked on checkbox, let the native 'change' handler below do the
      // toggle (it fires for both mouse and keyboard activation). Calling
      // _toggleCategory here too double-fires the whole category toggle for
      // a single click (change handler also targets .category-checkbox),
      // which double-enables/disables every overlay in the category and can
      // race the async data fetch into announcing a stale count. Only
      // suppress propagation so the click doesn't also collapse/expand the
      // category header below.
      if (e.target === checkbox || e.target.closest('.category-checkbox')) {
        e.stopPropagation();
        return;
      }

      // Otherwise expand/collapse the category
      this.categoryExpanded[categoryId] = !this.categoryExpanded[categoryId];
      const subList = wrapper.querySelector('.overlay-sub-list');
      const toggle = categoryHeader.querySelector('.category-toggle');

      subList.style.display = this.categoryExpanded[categoryId] ? 'block' : 'none';
      toggle.textContent = this.categoryExpanded[categoryId] ? '-' : '+';
    });

    // Individual overlay checkbox changes
    this.list.addEventListener('change', (e) => {
      const checkbox = e.target;
      if (checkbox.type !== 'checkbox') return;

      // Handle category checkbox
      if (checkbox.classList.contains('category-checkbox')) {
        const categoryId = checkbox.dataset.categoryId;
        this._toggleCategory(categoryId, checkbox.checked);
        return;
      }

      // Handle individual overlay checkbox
      const overlayId = checkbox.dataset.overlayId;
      if (!overlayId) return;

      // Check if placeholder
      const overlay = ALL_OVERLAYS.find(o => o.id === overlayId);
      if (overlay?.placeholder) {
        checkbox.checked = false;
        return;
      }

      if (checkbox.checked) {
        this.activeOverlays.add(overlayId);
      } else {
        this.activeOverlays.delete(overlayId);
      }
      this._rememberCurrentLaneState();

      console.log('Overlay toggled:', overlayId, checkbox.checked);
      console.log('Active overlays:', Array.from(this.activeOverlays));

      // Update parent category checkbox state
      this._updateCategoryCheckbox(overlayId);

      // Notify listeners
      this._notifyListeners(overlayId, checkbox.checked);

      // Ops camera assist: enabling an overlay refits to the active set.
      this._maybeAutoFocusOnEnable(overlayId, checkbox.checked);

      // Persist current-session lane state
      this._saveState();
    });
  },

  /**
   * Ops-only camera assist for user toggles: when overlay(s) with a current
   * Ops snapshot are enabled, refit to the union of all active overlay
   * snapshots. Never runs on disable, and never runs outside the Ops lane
   * (see shouldAutoFocusOnOverlayEnable for the mode policy). Shared by both
   * the single-overlay toggle path and the category (batch) toggle path.
   * @param {string[]} overlayIds - Overlay ids just enabled.
   * @private
   */
  _watchForOpsFocusData(overlayIds) {
    const ids = (overlayIds || []).filter(Boolean);
    if (!ids.length) return;
    if (!shouldAutoFocusOnOverlayEnable(this.currentLaneMode)) return;
    // Enabling a global grid/field overlay means "show me the global
    // picture" regardless of what else is active.
    if (ids.some((id) => GLOBAL_FOCUS_OVERLAY_IDS.has(id))) {
      focusGlobalOverlayView();
      return;
    }
    if (ids.some((id) => getRenderedOpsGeojson(id))) {
      focusActiveOpsOverlays();
      return;
    }
    // First enable races the overlay's async data load (the toggle handler
    // runs synchronously; handleOverlayChange fetches later, and cold loads
    // can take 10s+). Watch briefly for the features to land, then fit once.
    // A newer toggle replaces any pending watcher; disable cancels it.
    window.clearInterval(this._autoFocusWatchTimer);
    const startedAt = Date.now();
    this._autoFocusWatchTimer = window.setInterval(() => {
      const expired = Date.now() - startedAt > 20000;
      const cancelled = !ids.some((id) => this.activeOverlays.has(id))
        || !shouldAutoFocusOnOverlayEnable(this.currentLaneMode);
      if (expired || cancelled) {
        window.clearInterval(this._autoFocusWatchTimer);
        return;
      }
      if (ids.some((id) => getRenderedOpsGeojson(id))) {
        window.clearInterval(this._autoFocusWatchTimer);
        focusActiveOpsOverlays();
      }
    }, 500);
  },

  /**
   * Ops-only camera assist for a single overlay toggle. See
   * _watchForOpsFocusData for the shared watcher semantics.
   * @private
   */
  _maybeAutoFocusOnEnable(overlayId, isActive) {
    if (!isActive) return;
    this._watchForOpsFocusData([overlayId]);
  },

  /**
   * Toggle all overlays in a category.
   * @private
   */
  _toggleCategory(categoryId, active) {
    const category = CATEGORIES.find(c => c.id === categoryId);
    if (!category || !category.isCategory) return;

    let anyEnabled = false;
    const enabledOverlayIds = [];
    for (const overlay of category.overlays) {
      if (overlay.locked || overlay.placeholder) continue;

      const wasActive = this.activeOverlays.has(overlay.id);

      if (active) {
        this.activeOverlays.add(overlay.id);
      } else {
        this.activeOverlays.delete(overlay.id);
      }

      // Update individual checkbox
      const checkbox = this.list.querySelector(`input[data-overlay-id="${overlay.id}"]`);
      if (checkbox) {
        checkbox.checked = active;
      }

      // Notify if state changed
      if (wasActive !== active) {
        anyEnabled = anyEnabled || active;
        if (active) enabledOverlayIds.push(overlay.id);
        this._notifyListeners(overlay.id, active, {
          categoryBatch: {
            categoryId,
            active,
            overlayIds: category.overlays
              .filter((item) => !item.locked && !item.placeholder)
              .map((item) => item.id),
          }
        });
      }
    }
    this._rememberCurrentLaneState();

    // Update category checkbox (clear indeterminate)
    const catCheckbox = this.list.querySelector(`input[data-category-id="${categoryId}"]`);
    if (catCheckbox) {
      catCheckbox.indeterminate = false;
      catCheckbox.checked = active;
    }

    console.log('Category toggled:', categoryId, active);
    console.log('Active overlays:', Array.from(this.activeOverlays));

    // Ops camera assist: watch the newly-enabled overlays in the category
    // and refit once any of them has rendered data (see
    // _watchForOpsFocusData; mirrors the single-overlay toggle path so a
    // cold first enable via the category checkbox still moves the camera).
    if (anyEnabled) {
      this._watchForOpsFocusData(enabledOverlayIds);
    }

    // Persist current-session lane state
    this._saveState();
  },

  /**
   * Update category checkbox based on child states.
   * @private
   */
  _updateCategoryCheckbox(overlayId) {
    // Find which category this overlay belongs to
    for (const cat of CATEGORIES) {
      if (!cat.isCategory) continue;

      const overlay = cat.overlays.find(o => o.id === overlayId);
      if (!overlay) continue;

      // Count active non-placeholder overlays
      const nonPlaceholders = cat.overlays.filter(o => !o.placeholder);
      const activeCount = nonPlaceholders.filter(o => this.activeOverlays.has(o.id)).length;
      const allActive = activeCount === nonPlaceholders.length;
      const someActive = activeCount > 0 && !allActive;

      const checkbox = this.list.querySelector(`input[data-category-id="${cat.id}"]`);
      if (checkbox) {
        checkbox.checked = allActive;
        checkbox.indeterminate = someActive;
      }
      break;
    }
  },

  /**
   * Toggle an overlay on/off.
   * @param {string} overlayId - Overlay ID
   */
  toggle(overlayId) {
    const overlay = ALL_OVERLAYS.find(o => o.id === overlayId);
    if (!overlay || overlay.locked || overlay.placeholder) return;

    if (this.activeOverlays.has(overlayId)) {
      this.activeOverlays.delete(overlayId);
    } else {
      this.activeOverlays.add(overlayId);
    }
    this._rememberCurrentLaneState();

    // Update checkbox
    const checkbox = this.list?.querySelector(`input[data-overlay-id="${overlayId}"]`);
    if (checkbox) {
      checkbox.checked = this.activeOverlays.has(overlayId);
    }

    // Update category checkbox
    this._updateCategoryCheckbox(overlayId);

    // Notify listeners
    this._notifyListeners(overlayId, this.activeOverlays.has(overlayId));

    // Ops camera assist: enabling an overlay refits to the active set.
    this._maybeAutoFocusOnEnable(overlayId, this.activeOverlays.has(overlayId));

    // Persist current-session lane state
    this._saveState();
  },

  /**
   * Check if an overlay is active.
   * @param {string} overlayId - Overlay ID
   * @returns {boolean}
   */
  isActive(overlayId) {
    return this.activeOverlays.has(overlayId);
  },

  /**
   * Get list of active overlay IDs.
   * Used by preprocessor for chat context.
   * @returns {string[]}
   */
  getActiveOverlays() {
    return Array.from(this.activeOverlays);
  },

  getVisibleOverlays() {
    return VISIBLE_OVERLAYS.map((overlay) => ({ ...overlay }));
  },

  /**
   * Get overlay configuration by ID.
   * @param {string} overlayId - Overlay ID
   * @returns {Object|null}
   */
  getOverlayConfig(overlayId) {
    return ALL_OVERLAYS.find(o => o.id === overlayId) || null;
  },

  refreshVisibility() {
    if (!ALL_CATEGORIES.length) return;

    this.currentLaneMode = getCurrentOverlayLaneMode();
    CATEGORIES = filterCategoriesForCurrentMode(ALL_CATEGORIES);
    VISIBLE_OVERLAYS = getAllOverlaysFromCategories(CATEGORIES);

    const visibleOverlayIds = new Set(VISIBLE_OVERLAYS.map((overlay) => overlay.id));
    const removed = [];
    for (const overlayId of Array.from(this.activeOverlays)) {
      if (!visibleOverlayIds.has(overlayId)) {
        this.activeOverlays.delete(overlayId);
        removed.push(overlayId);
      }
    }

    const nextCategoryExpanded = {};
    for (const category of CATEGORIES) {
      if (category.isCategory) {
        nextCategoryExpanded[category.id] = this.categoryExpanded[category.id] ?? category.expanded ?? false;
      }
    }
    this.categoryExpanded = nextCategoryExpanded;
    this._rememberCurrentLaneState();

    if (this.initialized) {
      this._buildUI();
      this._setupEvents();
      for (const overlayId of removed) {
        this._notifyListeners(overlayId, false, {
          suppressStatusMessage: true,
          systemTransition: true
        });
      }
      this._saveState();
    }
  },

  syncToCurrentMode() {
    const nextMode = getCurrentOverlayLaneMode();
    const previousOverlays = new Set(this.activeOverlays);
    this._rememberCurrentLaneState();
    this.currentLaneMode = nextMode;
    if (!this._restoreState(nextMode)) {
      this.applyLaneDefaults(nextMode);
    }
    this.refreshVisibility();

    const nextOverlays = new Set(this.activeOverlays);
    for (const overlayId of previousOverlays) {
      if (!nextOverlays.has(overlayId)) {
        this._notifyListeners(overlayId, false, {
          suppressStatusMessage: true,
          systemTransition: true
        });
      }
    }
    for (const overlayId of nextOverlays) {
      if (!previousOverlays.has(overlayId)) {
        this._notifyListeners(overlayId, true, {
          suppressStatusMessage: true,
          systemTransition: true
        });
      }
    }
  },

  /**
   * Add a listener for overlay changes.
   * @param {Function} callback - Called with (overlayId, isActive)
   */
  addListener(callback) {
    this.listeners.push(callback);
  },

  showOverlay(overlayId, mode = this.currentLaneMode) {
    const normalizedMode = String(mode || this.currentLaneMode || 'explore').trim().toLowerCase() || 'explore';
    let shown = laneShownAdjustments.get(normalizedMode);
    if (!shown) {
      shown = new Set();
      laneShownAdjustments.set(normalizedMode, shown);
    }
    const hadOverlay = shown.has(overlayId);
    shown.add(overlayId);
    if (!hadOverlay && normalizedMode === this.currentLaneMode) {
      this.refreshVisibility();
    }
    return !hadOverlay;
  },

  promoteOverlay(overlayId, mode = this.currentLaneMode) {
    return this.showOverlay(overlayId, mode);
  },

  applyAccountOverlayPolicy(mode = this.currentLaneMode) {
    accountOverlayPolicyEnabled = true;
    const normalizedMode = String(mode || this.currentLaneMode || 'explore').trim().toLowerCase() || 'explore';
    this.currentLaneMode = normalizedMode;
    const accountEnabled = getBaseEnabledOverlayIdsForMode(normalizedMode);
    for (const overlayId of accountEnabled) {
      this.showOverlay(overlayId, normalizedMode);
      this.activeOverlays.add(overlayId);
    }
    this._rememberCurrentLaneState();
    this.refreshVisibility();
  },

  /**
   * Remove a listener.
   * @param {Function} callback
   */
  removeListener(callback) {
    const index = this.listeners.indexOf(callback);
    if (index >= 0) {
      this.listeners.splice(index, 1);
    }
  },

  /**
   * Notify all listeners of an overlay change.
   * @private
   */
  _notifyListeners(overlayId, isActive, options = {}) {
    for (const listener of this.listeners) {
      try {
        listener(overlayId, isActive, options);
      } catch (err) {
        console.error('OverlaySelector listener error:', err);
      }
    }
  },

  /**
   * Expand the overlay list.
   */
  expand() {
    this.expanded = true;
    if (this.list) {
      this.list.style.display = 'block';
    }
    if (this.header) {
      this.header.querySelector('.overlay-toggle').textContent = '-';
    }
  },

  /**
   * Collapse the overlay list.
   */
  collapse() {
    this.expanded = false;
    if (this.list) {
      this.list.style.display = 'none';
    }
    if (this.header) {
      this.header.querySelector('.overlay-toggle').textContent = '+';
    }
  },

  /**
   * Set overlay state programmatically.
   * @param {string} overlayId - Overlay ID
   * @param {boolean} active - Active state
   */
  setActive(overlayId, active) {
    const overlay = ALL_OVERLAYS.find(o => o.id === overlayId);
    if (!overlay || overlay.locked || overlay.placeholder) return;

    if (active) {
      this.showOverlay(overlayId, this.currentLaneMode);
      this.activeOverlays.add(overlayId);
    } else {
      this.activeOverlays.delete(overlayId);
    }
    this._rememberCurrentLaneState();

    // Update checkbox
    const checkbox = this.list?.querySelector(`input[data-overlay-id="${overlayId}"]`);
    if (checkbox) {
      checkbox.checked = active;
    }

    // Update category checkbox
    this._updateCategoryCheckbox(overlayId);

    // Persist current-session lane state
    this._saveState();
  },

  _rememberCurrentLaneState() {
    this.laneOverlayStates.set(this.currentLaneMode, Array.from(this.activeOverlays));
  },

  /**
   * Save active overlays in memory for the current runtime session only.
   * @private
   */
  _saveState() {
    const data = Array.from(this.activeOverlays);
    this.laneOverlayStates.set(this.currentLaneMode, data);
  },

  /**
   * Restore active overlays from in-memory lane state only.
   * @private
   * @returns {boolean} True if state was restored, false otherwise
   */
  _restoreState(mode = this.currentLaneMode) {
    this.activeOverlays.clear();
    const raw = this.laneOverlayStates.get(mode);
    if (Array.isArray(raw)) {
      for (const id of raw) {
        if (ALL_OVERLAYS.find(o => o.id === id)) {
          this.activeOverlays.add(id);
        }
      }
      this.laneOverlayStates.set(mode, Array.from(this.activeOverlays));
      console.log('OverlaySelector: Restored in-memory state for lane', mode, Array.from(this.activeOverlays));
      return true;
    }
    return false;
  },

  /**
   * Clear current-session lane state and reset to defaults.
   * Called by New Chat button.
   */
  clearState() {
    this.laneOverlayStates.clear();
    laneShownAdjustments.clear();

    // Clear current state
    const previousOverlays = Array.from(this.activeOverlays);
    this.activeOverlays.clear();

    // Reset to defaults
    this.applyLaneDefaults(this.currentLaneMode);

    // Rebuild UI to reflect reset state
    if (this.list) {
      this._buildUI();
      this._setupEvents();
    }

    // Notify listeners of changes
    for (const id of previousOverlays) {
      if (!this.activeOverlays.has(id)) {
        this._notifyListeners(id, false);
      }
    }
    for (const id of this.activeOverlays) {
      if (!previousOverlays.includes(id)) {
        this._notifyListeners(id, true);
      }
    }

    console.log('OverlaySelector: State cleared, reset to defaults');
  }
};

// Expose globally for ViewportLoader to check active overlays
window.OverlaySelector = OverlaySelector;
