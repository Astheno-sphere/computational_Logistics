export const SURFACE_MESSAGE_PROFILES = {
  admin_layers: {
    label: 'Admin Layers',
    singular: 'boundary',
    plural: 'boundaries',
    exploreActiveDescription: 'published administrative geometry for this viewport',
    exploreHints: 'Move or zoom the map to cross between global and country-level detail.',
    exploreExamples: ['show administrative boundaries in Canada', 'zoom into local boundaries'],
  },
  earthquakes: {
    label: 'Earthquakes',
    singular: 'earthquake',
    plural: 'earthquakes',
    exploreActiveDescription: 'historical earthquake events',
    exploreHints: 'Ask chat to filter by magnitude, region, or time.',
    exploreExamples: ['show earthquakes near Japan', 'show earthquakes above magnitude 6'],
  },
  hurricanes: {
    label: 'Hurricanes',
    singular: 'storm track',
    plural: 'storm tracks',
    exploreActiveDescription: 'storm tracks and named storm history',
    exploreHints: 'Ask chat to focus on one basin, one storm, or the strongest seasons.',
    exploreExamples: ['show Atlantic hurricanes', 'focus on the strongest recent storms'],
  },
  hurricanes_live: {
    label: 'Hurricanes',
    singular: 'storm track',
    plural: 'storm tracks',
    exploreActiveDescription: 'live storm tracks, recent advisory history, and forecasts',
    exploreHints: 'Ask chat to focus on one storm, one basin, or the strongest active storms.',
    exploreExamples: ['show active hurricanes', 'focus on the strongest storm'],
  },
  volcanoes: {
    label: 'Volcanoes',
    singular: 'volcano event',
    plural: 'volcano events',
    exploreActiveDescription: 'eruption and volcano history',
    exploreHints: 'Ask chat to filter by region, activity, or eruption strength.',
    exploreExamples: ['show volcanoes in Indonesia', 'show the strongest recent eruptions'],
  },
  wildfires: {
    label: 'Wildfires',
    singular: 'wildfire event',
    plural: 'wildfire events',
    exploreActiveDescription: 'wildfire history and related fire events',
    exploreHints: 'Ask chat to filter by size, region, or recent activity.',
    exploreExamples: ['show the largest wildfires', 'focus on California fires'],
  },
  tsunamis: {
    label: 'Tsunamis',
    singular: 'tsunami event',
    plural: 'tsunami events',
    exploreActiveDescription: 'tsunami events and linked event context',
    exploreHints: 'Ask chat for linked earthquakes, recent history, or one region.',
    exploreExamples: ['show recent tsunamis', 'show linked earthquake events'],
  },
  tornadoes: {
    label: 'Tornadoes',
    singular: 'tornado event',
    plural: 'tornado events',
    exploreActiveDescription: 'tornado event history',
    exploreHints: 'Ask chat to filter by scale, date range, or region.',
    exploreExamples: ['show major tornadoes', 'show tornadoes in Oklahoma'],
  },
  floods: {
    label: 'Floods',
    singular: 'flood event',
    plural: 'flood events',
    exploreActiveDescription: 'flood event history',
    exploreHints: 'Ask chat to focus on one region, one year, or the biggest events.',
    exploreExamples: ['show major floods', 'focus on floods in Pakistan'],
  },
  landslides: {
    label: 'Landslides',
    singular: 'landslide event',
    plural: 'landslide events',
    exploreActiveDescription: 'landslide event history',
    exploreHints: 'Ask chat to filter by deaths, region, or time.',
    exploreExamples: ['show deadly landslides', 'focus on landslides in South America'],
  },
  demographics: {
    label: 'Demographics',
    singular: 'demographic area',
    plural: 'demographic areas',
    exploreActiveDescription: 'demographic comparison layers',
    exploreHints: 'Ask chat to compare metrics, change regions, or switch scale.',
    exploreExamples: ['compare population and income', 'show population by county'],
  },
  fema_declarations: {
    label: 'FEMA Declarations',
    singular: 'declaration record',
    plural: 'declaration records',
    exploreActiveDescription: 'FEMA disaster declaration history',
    exploreHints: 'Ask chat to filter by state, incident type, declaration year, or disaster number.',
    exploreExamples: ['show FEMA declarations in Florida', 'show wildfire declarations since 2020'],
  },
  risk: {
    label: 'NRI Risk',
    singular: 'county risk area',
    plural: 'county risk areas',
    exploreActiveDescription: 'FEMA National Risk Index county hazard layers',
    exploreHints: 'Ask chat to switch hazard types, compare counties, or explain the NRI score.',
    exploreExamples: ['show NRI wildfire risk', 'compare county risk in Texas'],
  },
  world_bank_wdi: {
    label: 'World Bank WDI',
    singular: 'country value',
    plural: 'country values',
    exploreActiveDescription: 'World Bank country indicator data',
    exploreHints: 'Ask for economy, health, education, environment, debt, infrastructure, or social indicators; you can also compare countries or choose a year.',
    exploreExamples: ['show GDP current USD', 'compare life expectancy by country', 'show internet access by country'],
  },
  distributed_manufacturing: {
    label: 'Distributed Manufacturing',
    singular: 'maker location',
    plural: 'maker locations',
    exploreActiveDescription: 'public makerspaces, fab labs, hackerspaces, and related locations',
    exploreHints: 'Ask chat to narrow by country, include one network, or focus on public spaces.',
    exploreExamples: ['show makerspaces in Germany', 'show Precious Plastic workshops'],
  },
  temperature: {
    label: 'Temperature',
    singular: 'temperature cell',
    plural: 'temperature cells',
    exploreActiveDescription: 'temperature grids and climate context',
    exploreHints: 'Ask chat to change the date, compare regions, or switch climate variables.',
    exploreExamples: ['show temperature in July 2024', 'compare heat across Europe'],
  },
  humidity: {
    label: 'Humidity',
    singular: 'humidity cell',
    plural: 'humidity cells',
    exploreActiveDescription: 'humidity grids and climate context',
    exploreHints: 'Ask chat to change the date, compare regions, or switch climate variables.',
    exploreExamples: ['show humidity this week', 'compare humidity across the Gulf Coast'],
  },
  'snow-depth': {
    label: 'Snow Depth',
    singular: 'snow cell',
    plural: 'snow cells',
    exploreActiveDescription: 'snow depth grids',
    exploreHints: 'Ask chat to change the date, compare regions, or focus on winter conditions.',
    exploreExamples: ['show snow depth in the Rockies', 'compare snow this winter'],
  },
  'ocean-sst-grid': {
    label: 'Ocean Temperature',
    singular: 'ocean temperature cell',
    plural: 'ocean temperature cells',
    exploreActiveDescription: 'ocean temperature grids',
    exploreHints: 'Ask chat to animate the range, compare basins, or focus on anomalies.',
    exploreExamples: ['show ocean temperature in the Pacific', 'animate recent SST changes'],
  },
  aurora: {
    label: 'Aurora',
    singular: 'aurora model cell',
    plural: 'aurora model cells',
    exploreActiveDescription: 'aurora conditions',
    exploreHints: 'Ask chat where aurora is most likely visible right now.',
    exploreExamples: ['where is aurora most likely visible right now?'],
  },
  buoys: {
    label: 'Ocean Buoys',
    singular: 'buoy station',
    plural: 'buoy stations',
    exploreActiveDescription: 'live ocean buoy observations',
    exploreHints: 'Ask chat to focus on sea temperature, wind, waves, or one coastal region.',
    exploreExamples: ['show warmest ocean buoys', 'focus on Gulf Coast buoys'],
  },
  airnow: {
    label: 'AirNow AQI', singular: 'reporting area', plural: 'reporting areas',
    exploreActiveDescription: 'preliminary AirNow reporting-area AQI',
    exploreHints: 'Ask chat to focus on a region or explain the current AQI categories.',
    exploreExamples: ['show the highest current AQI reporting areas', 'focus AirNow AQI on California'],
  },
  nws_alerts: {
    label: 'NWS Alerts',
    singular: 'alert',
    plural: 'alerts',
    exploreActiveDescription: 'live severe weather alerts',
    exploreHints: 'Ask chat to focus on one state or explain the alert mix.',
    exploreExamples: ['show alerts in Texas', 'explain the current alert mix'],
  },
  currency: {
    label: 'Currency',
    singular: 'country value',
    plural: 'country values',
    exploreActiveDescription: 'currency comparison layers',
    exploreHints: 'Ask chat to focus on one region, compare currencies, or list the biggest movers.',
    exploreExamples: ['compare currencies in South America', 'show the biggest movers'],
  }
};

export function getSurfaceMessageProfile(surfaceId) {
  const key = String(surfaceId || '').trim();
  return SURFACE_MESSAGE_PROFILES[key] || {
    label: key ? key.replace(/[-_]/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase()) : 'Overlay',
    singular: 'item',
    plural: 'items',
    exploreActiveDescription: 'map data',
    exploreHints: 'Ask chat to refine the view, focus on a region, or explain what is loaded.',
    exploreExamples: [],
  };
}

export function formatSurfaceLabel(surfaceId) {
  return getSurfaceMessageProfile(surfaceId).label;
}

export function buildExploreWelcomeStatusMessage() {
  return 'Explore is ready. This lane uses maintained published map data and historical event layers so you can see patterns in place, compare sources, and then narrow with chat. Try turning on an overlay or ask for one place, one time range, or one comparison.';
}

export function buildOverlayStatusMessage(overlayId, isActive, options = {}) {
  const profile = getSurfaceMessageProfile(overlayId);
  const loadedCount = Number(options.loadedCount);
  const mode = String(options.mode || 'explore').trim().toLowerCase() || 'explore';
  if (!isActive) {
    return `${profile.label} hidden now. Ask chat to bring it back, switch regions, or load another layer.`;
  }
  if (mode === 'explore') {
    if (Number.isFinite(loadedCount) && loadedCount >= 0) {
      return `${profile.label} active now. Loaded ${loadedCount.toLocaleString()} ${loadedCount === 1 ? profile.singular : profile.plural} from ${profile.exploreActiveDescription}. ${profile.exploreHints}`;
    }
    return `${profile.label} active now. Showing ${profile.exploreActiveDescription}. ${profile.exploreHints}`;
  }
  if (Number.isFinite(loadedCount) && loadedCount >= 0) {
    return `${profile.label} active now. Loaded ${loadedCount.toLocaleString()} ${loadedCount === 1 ? profile.singular : profile.plural}.`;
  }
  return `${profile.label} active now.`;
}
