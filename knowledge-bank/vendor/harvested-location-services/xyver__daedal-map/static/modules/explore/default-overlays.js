export function getExploreDefaultOverlayIds() {
  // Buoys are deliberately NOT here: the NDBC feed is a live snapshot
  // (Ops keeps it, with its retained ~72h window). Explore is history-first,
  // and buoys have no historical lane to participate in the time slider.
  // Revisit if a canonical buoy history source is ever built.
  return [
    // Published historical event families.
    'earthquakes',
    'tsunamis',
    'volcanoes',
    'hurricanes',
    'wildfires',
    'floods',
    'tornadoes',
    'risk',
    'admin_layers',

    // Published country/region indicator families. During catalog-surface QA
    // this list is intentionally broad: it keeps the tray populated even when
    // the anonymous overlay tree is empty but pack defaults are available.
    'economy',
    'nri',
    'cejst',
    'usa_industrial_activity',
    'usa_opportunity_zones',
    'world_factbook',
    'un_wpp',
    'world_bank_wdi',

    // Runtime-owned historical raster layers.  They remain distinct from the
    // catalog tree because their frame services are shared with Ops.
    'ocean-sst-grid',
    'land-temperature-grid',

    // Historical NWS is catalog-injected when the source is available. Keeping
    // the ID here lets the normal default-overlay path activate playback once
    // the published or WIP catalog exposes it.
    'nws_alerts_historical',
  ];
}
