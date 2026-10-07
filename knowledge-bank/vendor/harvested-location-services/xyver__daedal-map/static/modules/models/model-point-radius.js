/**
 * Point+Radius Model - Renders point events with optional radius circles.
 * Used for: Earthquakes, Volcanoes, Tornadoes, Tsunamis
 *
 * Display characteristics:
 * - Circle markers sized by magnitude/intensity
 * - Color coding by severity scale
 * - Optional felt/damage radius circles
 * - Glow effect for visibility on dark backgrounds
 */

import { CONFIG } from '../config.js';
import { DisasterPopup } from '../disaster-popup.js';
import { fetchMsgpack } from '../utils/fetch.js';
import { extendBoundsWithCoordinateList } from '../map-focus.mjs';

const DISASTER_ICON_SVGS = {
  earthquake: `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
      <path d="M4 13 L9 9 L11 13 L15 8 L20 11" fill="none" stroke="#f8fbff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M6 18 L9 15 L11 18 L14 14 L18 17" fill="none" stroke="#f8fbff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" opacity="0.88"/>
    </svg>
  `,
  volcano: `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
      <path d="M5 18 L10.5 10.5 L13.2 13.4 L15.2 10.2 L19 18 Z" fill="#f8fbff" opacity="0.94"/>
      <path d="M11.3 8.1 C10 6.7 10.4 5.1 12 4 C12.4 5.1 13.6 5.7 14.1 6.8 C14.6 7.9 14 9 12.8 9.8" fill="none" stroke="#f8fbff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  `,
  tsunami: `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
      <path d="M3.5 15.2 C6.6 9.4, 10.6 8.8, 13.5 14.8 C15.1 18.1, 18.1 18.4, 20.5 15.9" fill="none" stroke="#f8fbff" stroke-width="2.7" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M9.8 10.7 C11.1 7.1, 13.5 5.5, 16.1 5.2 C14.5 7.1, 14.8 9.5, 16.6 11.2" fill="none" stroke="#f8fbff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M3.8 19.1 C6.8 16.5, 10.2 16.7, 13 19.1 C14.8 20.5, 17.2 20.2, 19.5 18.7" fill="none" stroke="#f8fbff" stroke-width="2.15" stroke-linecap="round" opacity="0.92"/>
    </svg>
  `,
  wildfire: `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
      <path d="M12 3 C14.2 6.4 17.2 8.7 17.2 12.4 C17.2 16.1 14.9 19 12 19 C9.1 19 6.8 16.6 6.8 13.3 C6.8 10.8 8.1 8.8 10.2 6.9 C10.6 8.6 11.7 9.5 12.8 10.7 C13.5 8.4 13 5.9 12 3 Z" fill="#f8fbff"/>
    </svg>
  `,
  flood: `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
      <path d="M5 12 C7.3 9.4, 10 9.1, 12.2 11.8 C14 14.1, 16.3 14.2, 19 12.2" fill="none" stroke="#f8fbff" stroke-width="2.6" stroke-linecap="round"/>
      <path d="M5 17 C7.3 14.7, 10 14.5, 12.2 17 C14 19, 16.3 19, 19 17.2" fill="none" stroke="#f8fbff" stroke-width="2.2" stroke-linecap="round" opacity="0.92"/>
    </svg>
  `,
  tornado: `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
      <path d="M4 7 H20" fill="none" stroke="#f8fbff" stroke-width="2.3" stroke-linecap="round"/>
      <path d="M6 10 H18" fill="none" stroke="#f8fbff" stroke-width="2.3" stroke-linecap="round" opacity="0.96"/>
      <path d="M8 13 H15" fill="none" stroke="#f8fbff" stroke-width="2.3" stroke-linecap="round" opacity="0.92"/>
      <path d="M10 16 H13" fill="none" stroke="#f8fbff" stroke-width="2.1" stroke-linecap="round" opacity="0.9"/>
      <path d="M11.5 18.2 L12 21" fill="none" stroke="#f8fbff" stroke-width="2" stroke-linecap="round"/>
    </svg>
  `,
  landslide: `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
      <path d="M5 18 L11 10 L19 10" fill="none" stroke="#f8fbff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="11.8" cy="13.5" r="1.5" fill="#f8fbff"/>
      <circle cx="15" cy="15.7" r="1.8" fill="#f8fbff" opacity="0.94"/>
      <circle cx="18" cy="18.2" r="1.3" fill="#f8fbff" opacity="0.88"/>
    </svg>
  `
};

const DISASTER_ICON_SCALE = 1.4;
const DISASTER_ICON_TYPE_SCALE = {
  volcano: 1.25,
  // Tsunamis are comparatively sparse at the 10-year Explore scale, so give
  // their wave mark enough visual weight to remain identifiable among points.
  // This is 1.5x the former 1.08 tsunami scale.
  tsunami: 1.62
};

// Dependencies set via setDependencies
let MapAdapter = null;
let TimeSlider = null;

export function setDependencies(deps) {
  MapAdapter = deps.MapAdapter;
  if (deps.TimeSlider) {
    TimeSlider = deps.TimeSlider;
  }
}

export const PointRadiusModel = {
  // Currently active event types (supports multiple overlays simultaneously)
  activeTypes: new Set(),

  // Click handler references for cleanup (per event type)
  clickHandlers: new Map(),  // eventType -> handler
  _mapClickHandler: null,
  iconLoadPromises: new Map(),

  // Selected event tracking
  selectedEventId: null,
  selectedEventType: null,

  // Aftershock sequence tracking
  activeSequenceId: null,
  sequenceChangeCallback: null,  // Called when sequence selection changes

  /**
   * Generate type-specific layer ID.
   * @param {string} baseId - Base ID like 'source', 'circle', 'radius-outer'
   * @param {string} eventType - Event type like 'earthquake', 'volcano'
   * @returns {string} Type-specific ID like 'earthquake-source'
   */
  _layerId(baseId, eventType) {
    return `${eventType}-${baseId}`;
  },

  _getCircleSortKey(eventType) {
    switch (eventType) {
      case 'earthquake':
        return ['coalesce', ['get', 'magnitude'], 0];
      case 'volcano':
        return ['coalesce', ['get', 'VEI'], 0];
      case 'tsunami':
        return ['log10', ['max', 1, ['coalesce', ['get', 'runup_count'], 1]]];
      case 'wildfire':
        return ['log10', ['max', 1, ['coalesce', ['get', 'area_km2'], 1]]];
      case 'flood':
        return ['log10', ['max', 1, ['coalesce', ['get', 'duration_days'], 1]]];
      case 'tornado':
        return ['to-number', ['slice', ['coalesce', ['get', 'tornado_scale'], 'EF0'], -1], 0];
      case 'landslide':
        return ['coalesce', ['get', 'intensity'], 0];
      default:
        return ['coalesce', ['get', 'year'], 0];
    }
  },

  _layerUsesDisasterIcon(eventType) {
    return Boolean(DISASTER_ICON_SVGS[eventType]);
  },

  _baseCircleOpacity(baseOpacity, eventType) {
    if (!this._layerUsesDisasterIcon(eventType)) {
      return baseOpacity;
    }
    return Math.max(0.14, baseOpacity * 0.2);
  },

  _baseCircleStrokeWidth(baseWidth, eventType) {
    if (!this._layerUsesDisasterIcon(eventType)) {
      return baseWidth;
    }
    return Math.max(0.5, baseWidth * 0.45);
  },

  _featureSortValue(feature, eventType) {
    const props = feature?.properties || {};
    switch (eventType) {
      case 'earthquake':
        return Number(props.magnitude) || 0;
      case 'volcano':
        return Number(props.VEI) || 0;
      case 'tsunami':
        return Number(props.runup_count) || 0;
      case 'wildfire':
        return Number(props.area_km2) || 0;
      case 'flood':
        return Number(props.duration_days) || 0;
      case 'tornado': {
        const raw = String(props.tornado_scale || 'EF0');
        const parsed = parseInt(raw.replace(/[^0-9]/g, ''), 10);
        return Number.isFinite(parsed) ? parsed : 0;
      }
      case 'landslide':
        return Number(props.intensity) || 0;
      default:
        return Number(props.year) || 0;
    }
  },

  _sortGeojsonForEventType(geojson, eventType) {
    const features = Array.isArray(geojson?.features) ? geojson.features : [];
    if (features.length <= 1) {
      return geojson;
    }
    return {
      ...geojson,
      features: [...features].sort((a, b) => this._featureSortValue(a, eventType) - this._featureSortValue(b, eventType))
    };
  },

  _pickBestFeatureCandidate(features, eventType) {
    const candidates = Array.isArray(features) ? features.filter(Boolean) : [];
    if (!candidates.length) return null;
    return candidates.reduce((best, candidate) => {
      if (!best) return candidate;
      return this._featureSortValue(candidate, eventType) > this._featureSortValue(best, eventType)
        ? candidate
        : best;
    }, null);
  },

  _iconLayerId(eventType) {
    return this._layerId('icon', eventType);
  },

  _iconImageId(eventType) {
    return `disaster-icon-${eventType}`;
  },

  _iconScaleForType(eventType) {
    return DISASTER_ICON_TYPE_SCALE[eventType] || 1;
  },

  _buildIconSizeExpr(eventType, iconSizeExpr) {
    const baseExpr = ['*', DISASTER_ICON_SCALE, this._iconScaleForType(eventType), iconSizeExpr];
    if (eventType === 'wildfire') {
      return [
        'interpolate', ['linear'], ['zoom'],
        0, ['*', baseExpr, 1],
        4, ['*', baseExpr, 1.5],
        5, ['*', baseExpr, 1.7],
        // Close wildfire inspection needs a clearly legible icon. At zoom 6
        // this is twice the prior scale, while map-wide scanning is unchanged.
        6, ['*', baseExpr, 3.6],
        8, ['*', baseExpr, 4],
        10, ['*', baseExpr, 5.2],
        12, ['*', baseExpr, 6.6],
        14, ['*', baseExpr, 8],
        16, ['*', baseExpr, 9.5]
      ];
    }
    return [
      'interpolate', ['linear'], ['zoom'],
      0, ['*', baseExpr, 1],
      4, ['*', baseExpr, 1.5],
      5, ['*', baseExpr, 1.7],
      8, ['*', baseExpr, 2],
      10, ['*', baseExpr, 3.2],
      12, ['*', baseExpr, 4.6],
      14, ['*', baseExpr, 6],
      16, ['*', baseExpr, 7.5]
    ];
  },

  _pointFilterForType(eventType) {
    if (eventType === 'wildfire' || eventType === 'flood') {
      return ['==', ['geometry-type'], 'Point'];
    }
    return ['==', ['geometry-type'], 'Point'];
  },

  _iconColorExprForType(eventType) {
    switch (eventType) {
      case 'earthquake':
        return [
          'interpolate', ['linear'], ['get', 'magnitude'],
          3.0, CONFIG.earthquakeColors.minor,
          4.0, CONFIG.earthquakeColors.light,
          5.0, CONFIG.earthquakeColors.moderate,
          6.0, CONFIG.earthquakeColors.strong,
          7.0, CONFIG.earthquakeColors.major
        ];
      case 'volcano': {
        const hasValidVEI = ['all', ['has', 'VEI'], ['!=', ['get', 'VEI'], null]];
        return [
          'case',
          hasValidVEI, [
            'interpolate', ['linear'], ['get', 'VEI'],
            0, '#ffffcc',
            1, '#ffeda0',
            2, '#fed976',
            3, '#feb24c',
            4, '#fd8d3c',
            5, '#f03b20',
            6, '#bd0026',
            7, '#800026'
          ],
          '#44ff44'
        ];
      }
      case 'tsunami': {
        const isSourceExpr = ['coalesce', ['get', 'is_source'], false];
        return [
          'case',
          ['==', isSourceExpr, true], '#1e88e5',
          '#42a5f5'
        ];
      }
      case 'wildfire':
        return [
          'interpolate', ['linear'],
          ['log10', ['max', 10, ['coalesce', ['get', 'area_km2'], 100]]],
          2, '#ff8800',
          3, '#ff4400',
          4, '#cc0000',
          4.5, '#880000'
        ];
      case 'flood':
        return [
          'interpolate', ['linear'],
          ['log10', ['max', 1, ['coalesce', ['get', 'duration_days'], 7]]],
          0, '#66b3ff',
          1, '#3399ff',
          1.5, '#0066cc',
          2, '#003366'
        ];
      case 'tornado': {
        const scaleNumExpr = [
          'to-number',
          ['slice', ['coalesce', ['get', 'tornado_scale'], 'EF0'], -1],
          0
        ];
        return [
          'interpolate', ['linear'], scaleNumExpr,
          0, '#98fb98',
          1, '#32cd32',
          2, '#ffd700',
          3, '#ff8c00',
          4, '#ff4500',
          5, '#8b0000'
        ];
      }
      case 'landslide':
        return [
          'interpolate', ['linear'],
          ['coalesce', ['get', 'intensity'], 1],
          1, '#cd853f',
          2, '#a0522d',
          3, '#8b4513',
          4, '#654321',
          5, '#3d2314'
        ];
      default:
        return '#f8fbff';
    }
  },

  _ensureDisasterIcon(eventType) {
    const map = MapAdapter?.map;
    if (!map || !this._layerUsesDisasterIcon(eventType)) {
      return Promise.resolve(false);
    }

    const imageId = this._iconImageId(eventType);
    if (map.hasImage(imageId)) {
      return Promise.resolve(true);
    }
    if (this.iconLoadPromises.has(imageId)) {
      return this.iconLoadPromises.get(imageId);
    }

    const svg = String(DISASTER_ICON_SVGS[eventType] || '').trim();
    if (!svg) {
      return Promise.resolve(false);
    }

    const promise = new Promise((resolve, reject) => {
      const img = new Image(24, 24);
      img.onload = () => {
        try {
          if (!map.hasImage(imageId)) {
            map.addImage(imageId, img, { pixelRatio: 2, sdf: true });
            console.log(`PointRadiusModel: Added disaster icon image ${imageId}`);
          }
          resolve(true);
        } catch (error) {
          reject(error);
        } finally {
          this.iconLoadPromises.delete(imageId);
        }
      };
      img.onerror = (error) => {
        this.iconLoadPromises.delete(imageId);
        reject(error);
      };
      img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
    });

    this.iconLoadPromises.set(imageId, promise);
    return promise;
  },

  _addDisasterIconLayer(eventType, iconSizeExpr, opacityExpr, filter = null) {
    const map = MapAdapter?.map;
    if (!map || !this._layerUsesDisasterIcon(eventType)) return;
    const sourceId = this._layerId('source', eventType);
    const layerId = this._iconLayerId(eventType);
    const imageId = this._iconImageId(eventType);
    const sortKey = this._getCircleSortKey(eventType);
    if (!map.getSource(sourceId) || map.getLayer(layerId) || !map.hasImage(imageId)) return;

    map.addLayer({
      id: layerId,
      type: 'symbol',
      source: sourceId,
      filter: filter || this._pointFilterForType(eventType),
      layout: {
        'icon-image': imageId,
        'icon-size': this._buildIconSizeExpr(eventType, iconSizeExpr),
        'icon-allow-overlap': true,
        'icon-ignore-placement': true,
        'icon-anchor': 'center',
        'symbol-sort-key': sortKey
      },
      paint: {
        'icon-opacity': opacityExpr,
        'icon-color': this._iconColorExprForType(eventType),
        'icon-halo-color': 'rgba(2, 8, 20, 0.92)',
        'icon-halo-width': 2.2,
        'icon-halo-blur': 0.6
      }
    });
    console.log(`PointRadiusModel: Added disaster icon layer ${layerId}`);

    const clickHandler = this.clickHandlers.get(eventType);
    if (clickHandler) {
      map.on('click', layerId, clickHandler);
    }

    map.on('mouseenter', layerId, () => {
      map.getCanvas().style.cursor = 'pointer';
    });
    map.on('mouseleave', layerId, () => {
      map.getCanvas().style.cursor = '';
    });
    map.on('mousemove', layerId, (e) => {
      if (TimeSlider?.isPlaying) return;
      if (e.features.length > 0 && !MapAdapter.popupLocked) {
        const props = e.features[0].properties;
        const html = DisasterPopup.buildHoverHtml(props, eventType);
        MapAdapter.showPopup([e.lngLat.lng, e.lngLat.lat], html);
      }
    });
    map.on('mouseleave', layerId, () => {
      if (!MapAdapter.popupLocked) {
        MapAdapter.hidePopup();
      }
    });
  },

  _ensureEventTypeIconLayer(eventType) {
    if (!this._layerUsesDisasterIcon(eventType)) return Promise.resolve(false);

    const addLayerForType = () => {
      switch (eventType) {
        case 'earthquake':
          this._addEarthquakeIconLayer(eventType);
          break;
        case 'volcano':
          this._addVolcanoIconLayer(eventType);
          break;
        case 'tsunami':
          this._addTsunamiIconLayer(eventType);
          break;
        case 'wildfire':
          this._addWildfireIconLayer(eventType);
          break;
        case 'flood':
          this._addFloodIconLayer(eventType);
          break;
        case 'tornado':
          this._addTornadoIconLayer(eventType);
          break;
        case 'landslide':
          this._addLandslideIconLayer(eventType);
          break;
        default:
          break;
      }

      const map = MapAdapter?.map;
      const iconLayerId = this._iconLayerId(eventType);
      if (map?.getLayer(iconLayerId)) {
        map.setLayoutProperty(iconLayerId, 'visibility', 'visible');
      }
      return true;
    };

    return this._ensureDisasterIcon(eventType)
      .then(() => {
        if (!this.activeTypes.has(eventType)) return false;
        const sourceStillExists = Boolean(MapAdapter?.map?.getSource(this._layerId('source', eventType)));
        if (!sourceStillExists) return false;
        return addLayerForType();
      })
      .catch((error) => {
        console.warn(`PointRadiusModel: Could not load ${eventType} icon`, error);
        return false;
      });
  },

  // Legacy single-type property for backwards compatibility
  get activeType() {
    return this.activeTypes.size > 0 ? [...this.activeTypes][0] : null;
  },
  set activeType(val) {
    // Legacy setter - add to set if truthy, otherwise handled by clearType
    if (val) this.activeTypes.add(val);
  },

  // Legacy single click handler for backwards compatibility
  get clickHandler() {
    return this.clickHandlers.size > 0 ? [...this.clickHandlers.values()][0] : null;
  },
  set clickHandler(val) {
    // Legacy setter - handled by type-specific handlers now
  },

  /**
   * Render point events on the map.
   * Supports multiple event types simultaneously (earthquakes + volcanoes + tornadoes, etc.)
   * @param {Object} geojson - GeoJSON FeatureCollection with Point features
   * @param {string} eventType - 'earthquake', 'volcano', 'tornado', etc.
   * @param {Object} options - {showFeltRadius, showDamageRadius, onEventClick}
   */
  render(geojson, eventType = 'earthquake', options = {}) {
    if (!MapAdapter?.map) {
      console.warn('PointRadiusModel: MapAdapter not available');
      return;
    }

    if (!geojson || !geojson.features || geojson.features.length === 0) {
      console.log(`PointRadiusModel: No ${eventType} features to display`);
      // Clear this type's layers if no data
      this.clearType(eventType);
      return;
    }

    const sortedGeojson = this._sortGeojsonForEventType(geojson, eventType);

    // Check if source already exists - if so, just update data (no flash)
    const sourceId = this._layerId('source', eventType);
    const existingSource = MapAdapter.map.getSource(sourceId);

    if (existingSource) {
      // Source exists - just update data, don't recreate layers
      this.activeTypes.add(eventType);
      existingSource.setData(sortedGeojson);
      this._ensureEventTypeIconLayer(eventType);
      return true;
    }

    // First time render - create source and layers
    // Track this type as active
    this.activeTypes.add(eventType);

    // Add type-specific source (allows multiple overlays)
    MapAdapter.map.addSource(sourceId, {
      type: 'geojson',
      data: sortedGeojson
    });

    // Build layers based on event type (pass eventType for type-specific layer IDs)
    if (eventType === 'earthquake') {
      this._addEarthquakeLayer(eventType, options);
    } else if (eventType === 'volcano') {
      this._addVolcanoLayer(eventType, options);
    } else if (eventType === 'tsunami') {
      this._addTsunamiLayer(eventType, options);
    } else if (eventType === 'wildfire') {
      this._addWildfireLayer(eventType, options);
    } else if (eventType === 'tornado') {
      this._addTornadoLayer(eventType, options);
    } else if (eventType === 'flood') {
      this._addFloodLayer(eventType, options);
    } else if (eventType === 'landslide') {
      this._addLandslideLayer(eventType, options);
    } else {
      this._addGenericEventLayer(eventType, options);
    }

    this._ensureEventTypeIconLayer(eventType);

    // Setup click handler - shows unified popup on click
    const clickHandler = (e) => {
      // Don't show popups during animation playback
      if (TimeSlider?.isPlaying) return;

      if (e.features.length > 0) {
        const pickedFeature = this._pickBestFeatureCandidate(e.features, eventType) || e.features[0];
        const props = pickedFeature.properties;

        // Use unified DisasterPopup system
        DisasterPopup.show([e.lngLat.lng, e.lngLat.lat], props, eventType);

        // Select this event - fills in the radius circles
        this._selectEvent(props.event_id);

        // Setup click handler for "View sequence" links in popup
        setTimeout(() => {
          const popupEl = document.querySelector('.maplibregl-popup-content');
          if (popupEl) {
            const seqLinks = popupEl.querySelectorAll('.view-sequence-link');
            seqLinks.forEach(link => {
              link.addEventListener('click', (evt) => {
                evt.preventDefault();
                const seqId = link.dataset.sequence;
                const eventId = link.dataset.eventid;
                if (seqId || eventId) {
                  // Notify sequence change listeners (SequenceAnimator handles viewport/display)
                  // Pass both sequenceId and eventId for accurate aftershock queries
                  this._notifySequenceChange(seqId, eventId);
                }
              });
            });

            // Setup click handler for "Find related earthquakes" link (volcano cross-link)
            const eqLinks = popupEl.querySelectorAll('.find-earthquakes-link');
            eqLinks.forEach(link => {
              link.addEventListener('click', async (evt) => {
                evt.preventDefault();
                const lat = parseFloat(link.dataset.lat);
                const lon = parseFloat(link.dataset.lon);
                const timestamp = link.dataset.timestamp;
                const year = parseInt(link.dataset.year);
                const volcanoName = link.dataset.volcano;

                // Update link to show loading state
                link.textContent = 'Searching...';
                link.style.pointerEvents = 'none';

                try {
                  // Build query URL - search 30 days before AND 60 days after eruption
                  let url = `/api/events/nearby-earthquakes?lat=${lat}&lon=${lon}&radius_km=150&min_magnitude=3.0`;
                  if (timestamp && timestamp !== 'null' && timestamp !== '') {
                    url += `&timestamp=${encodeURIComponent(timestamp)}&days_before=30&days_after=60`;
                  } else if (year) {
                    url += `&year=${year}`;
                  }

                  const data = await fetchMsgpack(url);

                  if (data.count > 0) {
                    // Found earthquakes - display them
                    link.textContent = `Found ${data.count} earthquakes`;
                    link.style.color = '#81c784';

                    // Notify listeners to display the earthquakes
                    // Use the volcano-triggered sequence ID pattern
                    const volcanoSeqId = `volcano-${volcanoName}-${year}`;
                    this._notifyVolcanoEarthquakes(data.features, volcanoSeqId, volcanoName, lat, lon);
                  } else {
                    link.textContent = 'No earthquakes found nearby';
                    link.style.color = '#999';
                  }
                } catch (err) {
                  console.error('Error fetching nearby earthquakes:', err);
                  link.textContent = 'Error searching';
                  link.style.color = '#f44336';
                }

                // Re-enable after delay
                setTimeout(() => {
                  link.style.pointerEvents = 'auto';
                }, 2000);
              });
            });

            // Setup click handler for "Find related volcanoes" link (earthquake cross-link)
            const volLinks = popupEl.querySelectorAll('.find-volcanoes-link');
            volLinks.forEach(link => {
              link.addEventListener('click', async (evt) => {
                evt.preventDefault();
                const lat = parseFloat(link.dataset.lat);
                const lon = parseFloat(link.dataset.lon);
                const timestamp = link.dataset.timestamp;
                const year = parseInt(link.dataset.year);

                // Update link to show loading state
                link.textContent = 'Searching...';
                link.style.pointerEvents = 'none';

                try {
                  // Build query URL - look for eruptions BEFORE the earthquake
                  let url = `/api/events/nearby-volcanoes?lat=${lat}&lon=${lon}&radius_km=150`;
                  if (timestamp && timestamp !== 'null' && timestamp !== '') {
                    url += `&timestamp=${encodeURIComponent(timestamp)}&days_before=60`;
                  } else if (year) {
                    url += `&year=${year}`;
                  }

                  const data = await fetchMsgpack(url);

                  if (data.count > 0) {
                    // Found volcanoes - display summary
                    const names = [...new Set(data.features.map(f => f.properties.volcano_name))];
                    const summary = names.length > 2
                      ? `${names.slice(0, 2).join(', ')} +${names.length - 2} more`
                      : names.join(', ');
                    link.textContent = `Found: ${summary}`;
                    link.style.color = '#81c784';

                    // Notify listeners to display the volcanoes
                    this._notifyNearbyVolcanoes(data.features, lat, lon);
                  } else {
                    link.textContent = 'No volcanoes found nearby';
                    link.style.color = '#999';
                  }
                } catch (err) {
                  console.error('Error fetching nearby volcanoes:', err);
                  link.textContent = 'Error searching';
                  link.style.color = '#f44336';
                }

                // Re-enable after delay
                setTimeout(() => {
                  link.style.pointerEvents = 'auto';
                }, 2000);
              });
            });

            // Setup click handler for "View runups" link (tsunami cross-link)
            const runupLinks = popupEl.querySelectorAll('.view-runups-link');
            runupLinks.forEach(link => {
              link.addEventListener('click', async (evt) => {
                evt.preventDefault();
                const eventId = link.dataset.event;

                // Update link to show loading state
                link.textContent = 'Loading runups...';
                link.style.pointerEvents = 'none';

                try {
                  // Fetch animation data (source + runups combined)
                  const url = `/api/tsunamis/${eventId}/animation`;
                  const data = await fetchMsgpack(url);

                  if (data.features && data.features.length > 1) {
                    // Found runups - update display
                    const runupCount = data.metadata?.runup_count || (data.features.length - 1);
                    link.textContent = `Showing ${runupCount} runups`;
                    link.style.color = '#81c784';

                    // Notify listeners to display the runups
                    this._notifyTsunamiRunups(data, eventId);
                  } else {
                    link.textContent = 'No runups recorded';
                    link.style.color = '#999';
                  }
                } catch (err) {
                  console.error('Error fetching tsunami runups:', err);
                  link.textContent = 'Error loading';
                  link.style.color = '#f44336';
                }

                // Re-enable after delay
                setTimeout(() => {
                  link.style.pointerEvents = 'auto';
                }, 2000);
              });
            });

            // Setup click handler for "View fire progression" link (wildfire animation)
            const fireLinks = popupEl.querySelectorAll('.view-fire-link');
            fireLinks.forEach(link => {
              link.addEventListener('click', async (evt) => {
                evt.preventDefault();
                const eventId = link.dataset.event;
                const duration = parseInt(link.dataset.duration) || 30;
                const timestamp = link.dataset.timestamp;
                const year = link.dataset.year;
                const latitude = link.dataset.lat ? parseFloat(link.dataset.lat) : null;
                const longitude = link.dataset.lon ? parseFloat(link.dataset.lon) : null;

                // Update link to show loading state
                link.textContent = 'Loading fire...';
                link.style.pointerEvents = 'none';

                try {
                  // First try to get daily progression data
                  const progressionUrl = year
                    ? `/api/wildfires/${eventId}/progression?year=${year}`
                    : `/api/wildfires/${eventId}/progression`;
                  const progressionData = await fetchMsgpack(progressionUrl);

                  // Handle both old format (snapshots array) and new FeatureCollection format
                  let snapshots, totalDays;
                  if (progressionData.type === 'FeatureCollection' && progressionData.features) {
                    // New format: convert features to snapshots format
                    snapshots = progressionData.features.map(f => ({
                      date: f.properties.date,
                      day_num: f.properties.day_num,
                      area_km2: f.properties.area_km2,
                      geometry: f.geometry
                    }));
                    totalDays = progressionData.metadata?.total_count || snapshots.length;
                  } else {
                    // Legacy format
                    snapshots = progressionData.snapshots;
                    totalDays = progressionData.total_days;
                  }

                  if (snapshots && snapshots.length > 0) {
                    // We have daily progression data - use it
                    link.textContent = `Starting (${totalDays} days)...`;
                    link.style.color = '#ff9800';
                    // Build normalized data for callback
                    const normalizedData = { snapshots, total_days: totalDays };
                    this._notifyFireProgression(normalizedData, eventId, timestamp, latitude, longitude);
                  } else {
                    // Fall back to single perimeter
                    const perimeterUrl = year
                      ? `/api/wildfires/${eventId}/perimeter?year=${year}`
                      : `/api/wildfires/${eventId}/perimeter`;
                    const perimeterData = await fetchMsgpack(perimeterUrl);

                    if (perimeterData.geometry) {
                      link.textContent = 'Starting animation...';
                      link.style.color = '#ff9800';
                      this._notifyFireAnimation(perimeterData, eventId, duration, timestamp, latitude, longitude);
                    } else {
                      link.textContent = 'No perimeter data';
                      link.style.color = '#999';
                    }
                  }
                } catch (err) {
                  console.error('Error fetching fire data:', err);
                  link.textContent = 'Error loading';
                  link.style.color = '#f44336';
                }

                // Re-enable after delay
                setTimeout(() => {
                  link.style.pointerEvents = 'auto';
                }, 2000);
              });
            });

            // Setup click handler for "View flood" link (flood animation)
            const floodLinks = popupEl.querySelectorAll('.view-flood-link');
            floodLinks.forEach(link => {
              link.addEventListener('click', async (evt) => {
                evt.preventDefault();
                const eventId = link.dataset.event;
                const durationDays = parseInt(link.dataset.duration) || 30;
                const startTime = link.dataset.start;
                const endTime = link.dataset.end;
                const eventName = link.dataset.name || '';
                const latitude = link.dataset.lat ? parseFloat(link.dataset.lat) : null;
                const longitude = link.dataset.lon ? parseFloat(link.dataset.lon) : null;

                // Update link to show loading state
                link.textContent = 'Loading flood...';
                link.style.pointerEvents = 'none';

                try {
                  // Fetch flood geometry
                  const geometryData = await fetchMsgpack(`/api/floods/${eventId}/geometry`);

                  if (geometryData.geometry) {
                    link.textContent = 'Starting animation...';
                    link.style.color = '#0066cc';
                    this._notifyFloodAnimation(geometryData, eventId, durationDays, startTime, endTime, latitude, longitude, eventName);
                  } else {
                    link.textContent = 'No geometry data';
                    link.style.color = '#999';
                  }
                } catch (err) {
                  console.error('Error fetching flood geometry:', err);
                  link.textContent = 'Error loading';
                  link.style.color = '#f44336';
                }

                // Re-enable after delay
                setTimeout(() => {
                  link.style.pointerEvents = 'auto';
                }, 2000);
              });
            });

            // Setup click handler for "View tornado track" link
            const tornadoLinks = popupEl.querySelectorAll('.view-tornado-track-link');
            tornadoLinks.forEach(link => {
              link.addEventListener('click', async (evt) => {
                evt.preventDefault();
                const eventId = link.dataset.event;

                // Update link to show loading state
                link.textContent = 'Loading track...';
                link.style.pointerEvents = 'none';

                try {
                  // Fetch tornado detail with track data
                  const url = `/api/tornadoes/${eventId}`;
                  const data = await fetchMsgpack(url);

                  // Handle both old format (data.track) and new FeatureCollection format
                  let trackData;
                  if (data.type === 'FeatureCollection' && data.features) {
                    // New format: find track feature in FeatureCollection
                    const trackFeature = data.features.find(f => f.geometry?.type === 'LineString');
                    const pointFeature = data.features.find(f => f.geometry?.type === 'Point');
                    if (trackFeature) {
                      trackData = {
                        track: trackFeature,
                        ...pointFeature?.properties
                      };
                    }
                  } else if (data.track && data.track.geometry) {
                    // Legacy format
                    trackData = data;
                  }

                  if (trackData && trackData.track) {
                    link.textContent = 'Showing track';
                    link.style.color = '#32cd32';

                    // Display the track on the map
                    this._displayTornadoTrack(trackData);
                  } else {
                    link.textContent = 'No track data';
                    link.style.color = '#999';
                  }
                } catch (err) {
                  console.error('Error fetching tornado track:', err);
                  link.textContent = 'Error loading';
                  link.style.color = '#f44336';
                }

                // Re-enable after delay
                setTimeout(() => {
                  link.style.pointerEvents = 'auto';
                }, 2000);
              });
            });

            // Setup click handler for "View tornado sequence/animate" link
            const sequenceLinks = popupEl.querySelectorAll('.view-tornado-sequence-link');
            sequenceLinks.forEach(link => {
              link.addEventListener('click', async (evt) => {
                evt.preventDefault();
                const eventId = link.dataset.event;
                const hasTrack = link.dataset.hastrack === 'true';
                const lat = parseFloat(link.dataset.lat) || null;
                const lon = parseFloat(link.dataset.lon) || null;
                const scale = link.dataset.scale || 'EF0';
                const timestamp = link.dataset.timestamp || null;

                // Update link to show loading state
                link.textContent = hasTrack ? 'Finding sequence...' : 'Starting animation...';
                link.style.pointerEvents = 'none';

                try {
                  // Fetch tornado sequence (linked tornadoes from same storm system)
                  const url = `/api/tornadoes/${eventId}/sequence`;
                  const data = await fetchMsgpack(url);

                  if (data.features && data.features.length > 0) {
                    // Has sequence or single tornado with track - animate it
                    const count = data.metadata?.total_count || data.features.length;
                    link.textContent = count > 1 ? `Animating ${count} linked` : 'Animating...';
                    link.style.color = '#ffa500';

                    // Notify controller to display the sequence
                    this._notifyTornadoSequence(data, eventId);
                  } else if (!hasTrack && lat && lon) {
                    // Point-only tornado - do a simple point animation
                    link.textContent = 'Animating point...';
                    link.style.color = '#ffa500';
                    this._notifyTornadoPointAnimation(eventId, lat, lon, scale, timestamp);
                  } else {
                    link.textContent = 'No animation data';
                    link.style.color = '#999';
                  }
                } catch (err) {
                  console.error('Error fetching tornado sequence:', err);
                  // If API failed but we have point data, do point animation
                  if (!hasTrack && lat && lon) {
                    link.textContent = 'Animating point...';
                    link.style.color = '#ffa500';
                    this._notifyTornadoPointAnimation(eventId, lat, lon, scale, timestamp);
                  } else {
                    link.textContent = 'Error loading';
                    link.style.color = '#f44336';
                  }
                }

                // Re-enable after delay
                setTimeout(() => {
                  link.style.pointerEvents = 'auto';
                }, 2000);
              });
            });
          }
        }, 50);

        // Call optional click callback
        if (options.onEventClick) {
          options.onEventClick(props);
        }
      }
    };

    // Use type-specific layer IDs for click handlers
    const circleLayerId = this._layerId('circle', eventType);
    const glowLayerId = this._layerId('circle-glow', eventType);
    const hitLayerId = this._layerId('circle-hit', eventType);
    const iconLayerId = this._iconLayerId(eventType);

    // Store handler reference per type for cleanup
    this.clickHandlers.set(eventType, clickHandler);

    // Register click handler on circle layer
    if (MapAdapter.map.getLayer(circleLayerId)) {
      MapAdapter.map.on('click', circleLayerId, clickHandler);
    }

    // Register click handler on the glow layer too so small dots are easier to click.
    if (MapAdapter.map.getLayer(glowLayerId)) {
      MapAdapter.map.on('click', glowLayerId, clickHandler);
    }

    if (MapAdapter.map.getLayer(hitLayerId)) {
      MapAdapter.map.on('click', hitLayerId, clickHandler);
    }

    if (MapAdapter.map.getLayer(iconLayerId)) {
      MapAdapter.map.on('click', iconLayerId, clickHandler);
    }

    // Click elsewhere to unlock popup and deselect (only setup once)
    if (!this._mapClickHandler) {
      this._mapClickHandler = (e) => {
        // Check if click was on any active event layer
        const layersToCheck = [];
        for (const type of this.activeTypes) {
          const circleId = this._layerId('circle', type);
          const glowId = this._layerId('circle-glow', type);
          const hitId = this._layerId('circle-hit', type);
          const iconId = this._iconLayerId(type);
          if (MapAdapter.map.getLayer(circleId)) layersToCheck.push(circleId);
          if (MapAdapter.map.getLayer(glowId)) layersToCheck.push(glowId);
          if (MapAdapter.map.getLayer(hitId)) layersToCheck.push(hitId);
          if (MapAdapter.map.getLayer(iconId)) layersToCheck.push(iconId);
        }

        if (layersToCheck.length > 0) {
          const features = MapAdapter.map.queryRenderedFeatures(e.point, {
            layers: layersToCheck
          });
          if (features.length === 0 && MapAdapter.popupLocked) {
            MapAdapter.popupLocked = false;
            MapAdapter.hidePopup();
            this._selectEvent(null);  // Clear selection
            this.highlightSequence(null);  // Clear sequence highlight
          }
        }
      };
      MapAdapter.map.on('click', this._mapClickHandler);
    }

    // Hover cursor (type-specific)
    if (MapAdapter.map.getLayer(circleLayerId)) {
      MapAdapter.map.on('mouseenter', circleLayerId, () => {
        MapAdapter.map.getCanvas().style.cursor = 'pointer';
      });
      MapAdapter.map.on('mouseleave', circleLayerId, () => {
        MapAdapter.map.getCanvas().style.cursor = '';
      });

      // Hover popup (only when not locked and not playing animation)
      MapAdapter.map.on('mousemove', circleLayerId, (e) => {
        if (TimeSlider?.isPlaying) return;
        if (e.features.length > 0 && !MapAdapter.popupLocked) {
          const props = e.features[0].properties;
          const html = DisasterPopup.buildHoverHtml(props, eventType);
          MapAdapter.showPopup([e.lngLat.lng, e.lngLat.lat], html);
        }
      });
      MapAdapter.map.on('mouseleave', circleLayerId, () => {
        if (!MapAdapter.popupLocked) {
          MapAdapter.hidePopup();
        }
      });
    }

    if (MapAdapter.map.getLayer(glowLayerId)) {
      MapAdapter.map.on('mouseenter', glowLayerId, () => {
        MapAdapter.map.getCanvas().style.cursor = 'pointer';
      });
      MapAdapter.map.on('mouseleave', glowLayerId, () => {
        MapAdapter.map.getCanvas().style.cursor = '';
      });

      MapAdapter.map.on('mousemove', glowLayerId, (e) => {
        if (TimeSlider?.isPlaying) return;
        if (e.features.length > 0 && !MapAdapter.popupLocked) {
          const props = e.features[0].properties;
          const html = DisasterPopup.buildHoverHtml(props, eventType);
          MapAdapter.showPopup([e.lngLat.lng, e.lngLat.lat], html);
        }
      });
      MapAdapter.map.on('mouseleave', glowLayerId, () => {
        if (!MapAdapter.popupLocked) {
          MapAdapter.hidePopup();
        }
      });
    }

    if (MapAdapter.map.getLayer(hitLayerId)) {
      MapAdapter.map.on('mouseenter', hitLayerId, () => {
        MapAdapter.map.getCanvas().style.cursor = 'pointer';
      });
      MapAdapter.map.on('mouseleave', hitLayerId, () => {
        MapAdapter.map.getCanvas().style.cursor = '';
      });

      MapAdapter.map.on('mousemove', hitLayerId, (e) => {
        if (TimeSlider?.isPlaying) return;
        if (e.features.length > 0 && !MapAdapter.popupLocked) {
          const props = e.features[0].properties;
          const html = DisasterPopup.buildHoverHtml(props, eventType);
          MapAdapter.showPopup([e.lngLat.lng, e.lngLat.lat], html);
        }
      });
      MapAdapter.map.on('mouseleave', hitLayerId, () => {
        if (!MapAdapter.popupLocked) {
          MapAdapter.hidePopup();
        }
      });
    }

    if (MapAdapter.map.getLayer(iconLayerId)) {
      MapAdapter.map.on('mouseenter', iconLayerId, () => {
        MapAdapter.map.getCanvas().style.cursor = 'pointer';
      });
      MapAdapter.map.on('mouseleave', iconLayerId, () => {
        MapAdapter.map.getCanvas().style.cursor = '';
      });

      MapAdapter.map.on('mousemove', iconLayerId, (e) => {
        if (TimeSlider?.isPlaying) return;
        if (e.features.length > 0 && !MapAdapter.popupLocked) {
          const props = e.features[0].properties;
          const html = DisasterPopup.buildHoverHtml(props, eventType);
          MapAdapter.showPopup([e.lngLat.lng, e.lngLat.lat], html);
        }
      });
      MapAdapter.map.on('mouseleave', iconLayerId, () => {
        if (!MapAdapter.popupLocked) {
          MapAdapter.hidePopup();
        }
      });
    }

    // Setup global popup event listeners (once)
    this._setupPopupEventListeners();

    console.log(`PointRadiusModel: Loaded ${geojson.features.length} ${eventType} events`);
  },

  /**
   * Add earthquake-specific layers (point + radius circles).
   *
   * Radii are pre-calculated in the data pipeline using empirical formulas:
   * - felt_radius_km: distance where shaking is noticeable (MMI II-III)
   * - damage_radius_km: distance with potential structural damage (MMI VI+)
   *
   * km-to-pixel conversion: pixels = km * 2^zoom / 156.5 (at equator)
   * @param {string} eventType - Event type for layer ID namespacing
   * @param {Object} options - Display options
   * @private
   */
  _addEarthquakeLayer(eventType, options = {}) {
    const colors = CONFIG.earthquakeColors;
    const map = MapAdapter.map;
    const sourceId = this._layerId('source', eventType);
    const sortKey = this._getCircleSortKey(eventType);

    // Color expression based on magnitude
    const colorExpr = [
      'interpolate', ['linear'], ['get', 'magnitude'],
      3.0, colors.minor,
      4.0, colors.light,
      5.0, colors.moderate,
      6.0, colors.strong,
      7.0, colors.major
    ];

    // Epicenter marker size - small fixed size (not geographic)
    const epicenterSize = [
      'interpolate', ['linear'], ['get', 'magnitude'],
      3.0, 3,
      5.0, 5,
      7.0, 8,
      8.0, 10
    ];

    // Helper: convert km to pixels at current zoom
    // Formula: pixels = km * 2^zoom / 156.5
    // Using exponential interpolation with base 2 for smooth scaling
    const kmToPixels = (kmExpr) => [
      'interpolate', ['exponential', 2], ['zoom'],
      0, ['/', kmExpr, 156.5],      // At zoom 0: very small
      5, ['/', kmExpr, 4.9],        // 2^5 / 156.5 = 0.204, so km/4.9
      10, ['*', kmExpr, 6.54],      // 2^10 / 156.5 = 6.54
      15, ['*', kmExpr, 209]        // 2^15 / 156.5 = 209
    ];

    // 1. FELT RADIUS - outer circle (thinner, less opaque)
    // Shows how far the earthquake could be felt
    if (options.showFeltRadius !== false) {
      map.addLayer({
        id: this._layerId('radius-outer', eventType),
        type: 'circle',
        source: sourceId,
        filter: ['>', ['get', 'felt_radius_km'], 0],
        paint: {
          'circle-radius': kmToPixels(['get', 'felt_radius_km']),
          'circle-color': 'transparent',
          'circle-stroke-color': colorExpr,  // Same color as magnitude
          'circle-stroke-width': 1.5,
          'circle-stroke-opacity': 0.35,
          'circle-pitch-alignment': 'map'  // Follow globe surface
        }
      });
    }

    // 2. DAMAGE RADIUS - inner circle (thicker, more opaque)
    // Shows potential structural damage zone (only M5+)
    if (options.showDamageRadius !== false) {
      map.addLayer({
        id: this._layerId('radius-inner', eventType),
        type: 'circle',
        source: sourceId,
        filter: ['>', ['get', 'damage_radius_km'], 0],
        paint: {
          'circle-radius': kmToPixels(['get', 'damage_radius_km']),
          'circle-color': 'transparent',
          'circle-stroke-color': colorExpr,  // Same color as magnitude
          'circle-stroke-width': 2.5,
          'circle-stroke-opacity': 0.7,
          'circle-pitch-alignment': 'map'  // Follow globe surface
        }
      });
    }

    // SELECTED EVENT LAYERS - filled circles for the selected event
    // These layers have a filter that initially matches nothing,
    // updated by _selectEvent() when an event is clicked

    // Selected felt radius - filled
    map.addLayer({
      id: this._layerId('radius-outer-selected', eventType),
      type: 'circle',
      source: sourceId,
      filter: ['==', ['get', 'event_id'], ''],  // Initially matches nothing
      paint: {
        'circle-radius': kmToPixels(['get', 'felt_radius_km']),
        'circle-color': colorExpr,
        'circle-opacity': 0.15,
        'circle-stroke-color': colorExpr,
        'circle-stroke-width': 2,
        'circle-stroke-opacity': 0.6,
        'circle-pitch-alignment': 'map'
      }
    });

    // Selected damage radius - filled
    map.addLayer({
      id: this._layerId('radius-inner-selected', eventType),
      type: 'circle',
      source: sourceId,
      filter: ['==', ['get', 'event_id'], ''],  // Initially matches nothing
      paint: {
        'circle-radius': kmToPixels(['get', 'damage_radius_km']),
        'circle-color': colorExpr,
        'circle-opacity': 0.25,
        'circle-stroke-color': colorExpr,
        'circle-stroke-width': 3,
        'circle-stroke-opacity': 0.9,
        'circle-pitch-alignment': 'map'
      }
    });

    // EXPANDING WAVEFRONT LAYERS - animated aftershock zone ripples
    // Uses _waveRadiusKm property set by filterByLifecycle() in overlay-controller.js
    // Aftershock zones expand slowly (~0.3-3 km/h based on magnitude) over days/weeks

    // Primary aftershock zone ring
    map.addLayer({
      id: this._layerId('wavefront', eventType),
      type: 'circle',
      source: sourceId,
      filter: ['all',
        ['has', '_waveRadiusKm'],
        ['>', ['get', '_waveRadiusKm'], 0]
      ],
      paint: {
        'circle-radius': kmToPixels(['get', '_waveRadiusKm']),
        'circle-color': 'transparent',
        'circle-stroke-color': colorExpr,
        'circle-stroke-width': 2.5,
        'circle-stroke-opacity': ['*', 0.7, ['coalesce', ['get', '_opacity'], 1.0]],
        'circle-pitch-alignment': 'map'  // Follow globe surface
      }
    });

    // Outer glow - aftershock influence zone
    map.addLayer({
      id: this._layerId('wavefront-glow', eventType),
      type: 'circle',
      source: sourceId,
      filter: ['all',
        ['has', '_waveRadiusKm'],
        ['>', ['get', '_waveRadiusKm'], 10]  // Only show when radius > 10km
      ],
      paint: {
        'circle-radius': kmToPixels(['+', ['get', '_waveRadiusKm'], 15]),
        'circle-color': colorExpr,
        'circle-opacity': ['*', 0.1, ['coalesce', ['get', '_opacity'], 1.0]],
        'circle-blur': 0.6,
        'circle-pitch-alignment': 'map'
      }
    });

    // Recency-based effects for animation
    // _recency: 1.5 = brand new (flash), 1.0 = recent, 0.0 = fading out
    // Use coalesce to default to 1.0 if _recency not present (normal display)
    const recencyExpr = ['coalesce', ['get', '_recency'], 1.0];

    // Lifecycle opacity: 1.0 = active, 0.0-1.0 = fading out
    // Set by filterByLifecycle() in overlay-controller.js
    const lifecycleOpacity = ['coalesce', ['get', '_opacity'], 1.0];

    // Opacity: multiply base * recency * lifecycle, cap at 1.0
    const opacityExpr = (baseOpacity) => [
      'min', 1.0,
      ['*', baseOpacity, ['*', recencyExpr, lifecycleOpacity]]
    ];

    // Size boost for new events: when recency > 1.0, add extra size
    // At recency 1.5: adds 50% extra size. At recency 1.0 or below: no boost.
    const sizeBoostExpr = (baseSize) => [
      '*', baseSize,
      ['max', 1.0, recencyExpr]  // Multiplier is 1.0-1.5 for flash, 1.0 otherwise
    ];

    // 3. EPICENTER GLOW - subtle glow behind the marker
    map.addLayer({
      id: this._layerId('circle-glow', eventType),
      type: 'circle',
      source: sourceId,
      layout: {
        'circle-sort-key': sortKey
      },
      paint: {
        'circle-radius': sizeBoostExpr(['+', epicenterSize, 4]),
        'circle-color': colorExpr,
        'circle-opacity': opacityExpr(0.3),  // Fade with recency, cap at 1.0
        'circle-blur': 1
      }
    });

    // 4. EPICENTER MARKER - small solid circle at exact location
    map.addLayer({
      id: this._layerId('circle', eventType),
      type: 'circle',
      source: sourceId,
      layout: {
        'circle-sort-key': sortKey
      },
      paint: {
        'circle-radius': sizeBoostExpr(epicenterSize),
        'circle-color': colorExpr,
        'circle-opacity': opacityExpr(this._baseCircleOpacity(0.9, eventType)),  // Fade with recency, cap at 1.0
        'circle-stroke-color': '#222222',
        'circle-stroke-width': this._baseCircleStrokeWidth(1, eventType)
      }
    });
  },

  _addEarthquakeIconLayer(eventType) {
    const recencyExpr = ['coalesce', ['get', '_recency'], 1.0];
    const lifecycleOpacity = ['coalesce', ['get', '_opacity'], 1.0];
    const iconSizeExpr = [
      'interpolate', ['linear'], ['get', 'magnitude'],
      3.0, 0.72,
      5.0, 0.92,
      7.0, 1.2,
      8.0, 1.36
    ];
    const iconOpacity = ['min', 1.0, ['*', 0.95, ['*', recencyExpr, lifecycleOpacity]]];
    this._addDisasterIconLayer(eventType, iconSizeExpr, iconOpacity);
  },

  /**
   * Add volcano-specific layers.
   * Uses VEI for color, felt_radius_km/damage_radius_km for radius circles.
   * @param {string} eventType - Event type for layer ID namespacing
   * @param {Object} options - Display options
   * @private
   */
  _addVolcanoLayer(eventType, options = {}) {
    const map = MapAdapter.map;
    const sourceId = this._layerId('source', eventType);
    const sortKey = this._getCircleSortKey(eventType);

    // Color by VEI (Volcanic Explosivity Index)
    const hasValidVEI = ['all', ['has', 'VEI'], ['!=', ['get', 'VEI'], null]];
    const colorExpr = [
      'case',
      hasValidVEI, [
        'interpolate', ['linear'], ['get', 'VEI'],
        0, '#ffffcc',   // Non-explosive - pale yellow
        1, '#ffeda0',   // Gentle - light yellow
        2, '#fed976',   // Explosive - yellow
        3, '#feb24c',   // Severe - orange
        4, '#fd8d3c',   // Cataclysmic - dark orange
        5, '#f03b20',   // Paroxysmal - red
        6, '#bd0026',   // Colossal - dark red
        7, '#800026'    // Super-colossal - maroon
      ],
      '#44ff44'  // No VEI - bright green
    ];

    const epicenterSize = [
      'case',
      hasValidVEI, [
        'interpolate', ['linear'], ['get', 'VEI'],
        0, 4, 3, 6, 5, 9, 7, 12
      ],
      6
    ];

    const kmToPixels = (kmExpr) => [
      'interpolate', ['exponential', 2], ['zoom'],
      0, ['/', kmExpr, 156.5],
      5, ['/', kmExpr, 4.9],
      10, ['*', kmExpr, 6.54],
      15, ['*', kmExpr, 209]
    ];

    if (options.showFeltRadius !== false) {
      map.addLayer({
        id: this._layerId('radius-outer', eventType),
        type: 'circle',
        source: sourceId,
        filter: ['>', ['get', 'felt_radius_km'], 0],
        paint: {
          'circle-radius': kmToPixels(['get', 'felt_radius_km']),
          'circle-color': 'transparent',
          'circle-stroke-color': colorExpr,
          'circle-stroke-width': 1.5,
          'circle-stroke-opacity': 0.35,
          'circle-pitch-alignment': 'map'
        }
      });
    }

    if (options.showDamageRadius !== false) {
      map.addLayer({
        id: this._layerId('radius-inner', eventType),
        type: 'circle',
        source: sourceId,
        filter: ['>', ['get', 'damage_radius_km'], 0],
        paint: {
          'circle-radius': kmToPixels(['get', 'damage_radius_km']),
          'circle-color': 'transparent',
          'circle-stroke-color': colorExpr,
          'circle-stroke-width': 2.5,
          'circle-stroke-opacity': 0.7,
          'circle-pitch-alignment': 'map'
        }
      });
    }

    map.addLayer({
      id: this._layerId('radius-outer-selected', eventType),
      type: 'circle',
      source: sourceId,
      filter: ['==', ['get', 'event_id'], ''],
      paint: {
        'circle-radius': kmToPixels(['get', 'felt_radius_km']),
        'circle-color': colorExpr,
        'circle-opacity': 0.15,
        'circle-stroke-color': colorExpr,
        'circle-stroke-width': 2,
        'circle-stroke-opacity': 0.6,
        'circle-pitch-alignment': 'map'
      }
    });

    map.addLayer({
      id: this._layerId('radius-inner-selected', eventType),
      type: 'circle',
      source: sourceId,
      filter: ['==', ['get', 'event_id'], ''],
      paint: {
        'circle-radius': kmToPixels(['get', 'damage_radius_km']),
        'circle-color': colorExpr,
        'circle-opacity': 0.25,
        'circle-stroke-color': colorExpr,
        'circle-stroke-width': 3,
        'circle-stroke-opacity': 0.9,
        'circle-pitch-alignment': 'map'
      }
    });

    // EXPANDING WAVEFRONT LAYERS - animated ash cloud/felt radius expansion
    // Uses _waveRadiusKm property set by filterByLifecycle() in overlay-controller.js
    // Target radius from data: VEI 2 ~23km, VEI 4 ~105km, VEI 6 ~478km, VEI 7 ~1021km

    // Primary ash cloud ring
    map.addLayer({
      id: this._layerId('wavefront', eventType),
      type: 'circle',
      source: sourceId,
      filter: ['all',
        ['has', '_waveRadiusKm'],
        ['>', ['get', '_waveRadiusKm'], 0]
      ],
      paint: {
        'circle-radius': kmToPixels(['get', '_waveRadiusKm']),
        'circle-color': 'transparent',
        'circle-stroke-color': colorExpr,
        'circle-stroke-width': 2,
        'circle-stroke-opacity': ['*', 0.6, ['coalesce', ['get', '_opacity'], 1.0]],
        'circle-pitch-alignment': 'map'  // Follow globe surface
      }
    });

    // Outer glow - ash fallout zone (diffuse impact area)
    map.addLayer({
      id: this._layerId('wavefront-glow', eventType),
      type: 'circle',
      source: sourceId,
      filter: ['all',
        ['has', '_waveRadiusKm'],
        ['>', ['get', '_waveRadiusKm'], 5]
      ],
      paint: {
        'circle-radius': kmToPixels(['+', ['get', '_waveRadiusKm'], 10]),
        'circle-color': colorExpr,
        'circle-opacity': ['*', 0.12, ['coalesce', ['get', '_opacity'], 1.0]],
        'circle-blur': 0.7,
        'circle-pitch-alignment': 'map'
      }
    });

    const recencyExpr = ['coalesce', ['get', '_recency'], 1.0];
    const lifecycleOpacity = ['coalesce', ['get', '_opacity'], 1.0];
    const opacityExpr = (baseOpacity) => [
      'min', 1.0,
      ['*', baseOpacity, ['*', recencyExpr, lifecycleOpacity]]
    ];
    const sizeBoostExpr = (baseSize) => ['*', baseSize, ['max', 1.0, recencyExpr]];

    map.addLayer({
      id: this._layerId('circle-glow', eventType),
      type: 'circle',
      source: sourceId,
      layout: {
        'circle-sort-key': sortKey
      },
      paint: {
        'circle-radius': sizeBoostExpr(['+', epicenterSize, 4]),
        'circle-color': colorExpr,
        'circle-opacity': opacityExpr(0.3),
        'circle-blur': 1
      }
    });

    map.addLayer({
      id: this._layerId('circle', eventType),
      type: 'circle',
      source: sourceId,
      layout: {
        'circle-sort-key': sortKey
      },
      paint: {
        'circle-radius': sizeBoostExpr(epicenterSize),
        'circle-color': colorExpr,
        'circle-opacity': opacityExpr(this._baseCircleOpacity(0.85, eventType)),
        'circle-stroke-color': '#333333',
        'circle-stroke-width': this._baseCircleStrokeWidth(1, eventType)
      }
    });
  },

  _addVolcanoIconLayer(eventType) {
    const recencyExpr = ['coalesce', ['get', '_recency'], 1.0];
    const lifecycleOpacity = ['coalesce', ['get', '_opacity'], 1.0];
    const iconSizeExpr = [
      'interpolate', ['linear'], ['coalesce', ['get', 'VEI'], 1],
      0, 0.58,
      2, 0.74,
      4, 1.03,
      6, 1.22
    ];
    const iconOpacity = ['min', 1.0, ['*', 0.96, ['*', recencyExpr, lifecycleOpacity]]];
    this._addDisasterIconLayer(eventType, iconSizeExpr, iconOpacity);
  },

  /**
   * Add tsunami-specific layers.
   * Handles both source epicenters (cyan) and coastal runup points (teal).
   * Uses is_source property to distinguish source from runup points.
   * Includes impact radius rings scaled by runup_count (log scale).
   * @param {string} eventType - Event type for layer ID namespacing
   * @param {Object} options - Display options
   * @private
   */
  _addTsunamiLayer(eventType, options = {}) {
    const map = MapAdapter.map;
    const sourceId = this._layerId('source', eventType);
    const sortKey = this._getCircleSortKey(eventType);

    // Recency-based effects for animation
    const recencyExpr = ['coalesce', ['get', '_recency'], 1.0];
    const lifecycleOpacity = ['coalesce', ['get', '_opacity'], 1.0];
    const opacityExpr = (baseOpacity) => [
      'min', 1.0,
      ['*', baseOpacity, ['*', recencyExpr, lifecycleOpacity]]
    ];
    const sizeBoostExpr = (baseSize) => ['*', baseSize, ['max', 1.0, recencyExpr]];

      // Colors: Source = deep blue-cyan, Runup = ocean blue
    // Use coalesce to handle boolean or truthy check
    const isSourceExpr = ['coalesce', ['get', 'is_source'], false];
    const colorExpr = [
      'case',
      ['==', isSourceExpr, true], '#1e88e5',  // Strong blue for source
      '#42a5f5'  // Lighter ocean blue for runups
    ];

    // Size based on runup_count (for sources) or water_height_m (for runups)
    // Log scale for runup count: 1->4, 10->7, 100->10, 1000->13, 5000->16
    // Increased range for more visible size difference
    const sizeExpr = [
      'case',
      ['==', isSourceExpr, true],
      // Source: size by runup_count (log scale for wide range 0-6000+)
      [
        'interpolate', ['linear'],
        ['log10', ['max', 1, ['coalesce', ['get', 'runup_count'], 1]]],
        0, 4,      // 1 runup = 4px
        1, 7,      // 10 runups = 7px
        2, 10,     // 100 runups = 10px
        3, 14,     // 1000 runups = 14px
        3.7, 18    // 5000+ runups = 18px (largest)
      ],
      // Runup: size by water height
      [
        'interpolate', ['linear'], ['coalesce', ['get', 'water_height_m'], 1],
        0, 4,
        5, 8,
        10, 12,
        20, 16
      ]
    ];

    // Helper: convert km to pixels at current zoom (same as earthquakes)
    // Formula: pixels = km * 2^zoom / 156.5
    const kmToPixels = (kmExpr) => [
      'interpolate', ['exponential', 2], ['zoom'],
      0, ['/', kmExpr, 156.5],
      5, ['/', kmExpr, 4.9],
      10, ['*', kmExpr, 6.54],
      15, ['*', kmExpr, 209]
    ];

    // Impact radius in km based on runup_count (log scale)
    // More runups = wider impact = larger ring
    // 1 runup = 30km, 10 = 100km, 100 = 300km, 1000 = 800km, 5000+ = 1500km
    const impactRadiusKm = [
      'interpolate', ['linear'],
      ['log10', ['max', 1, ['coalesce', ['get', 'runup_count'], 1]]],
      0, 30,       // 1 runup = 30km
      1, 100,      // 10 runups = 100km
      2, 300,      // 100 runups = 300km
      3, 800,      // 1000 runups = 800km
      3.7, 1500    // 5000+ runups = 1500km
    ];

    // 1. CONNECTION LINES (source to runups) - optional
    if (options.showConnections !== false) {
      map.addLayer({
        id: this._layerId('connections', eventType),
        type: 'line',
        source: sourceId,
        filter: ['==', ['geometry-type'], 'LineString'],
        paint: {
          'line-color': '#26c6da',
          'line-width': 1.5,
          'line-opacity': opacityExpr(0.4),
          'line-dasharray': [2, 2]
        }
      });
    }

    // 2. IMPACT RADIUS RING - shows tsunami reach based on runup_count
    // Only for source events (is_source: true)
    map.addLayer({
      id: this._layerId('radius-outer', eventType),
      type: 'circle',
      source: sourceId,
      filter: ['all',
        ['==', ['geometry-type'], 'Point'],
        ['==', ['get', 'is_source'], true],
        ['>', ['coalesce', ['get', 'runup_count'], 0], 0]
      ],
      paint: {
        'circle-radius': kmToPixels(impactRadiusKm),
        'circle-color': 'transparent',
        'circle-stroke-color': '#00bcd4',  // Cyan ring
        'circle-stroke-width': 1.5,
        'circle-stroke-opacity': opacityExpr(0.35),
        'circle-pitch-alignment': 'map'  // Follow globe surface
      }
    });

    // 3. INNER IMPACT RING - smaller ring for high-impact events (100+ runups)
    map.addLayer({
      id: this._layerId('radius-inner', eventType),
      type: 'circle',
      source: sourceId,
      filter: ['all',
        ['==', ['geometry-type'], 'Point'],
        ['==', ['get', 'is_source'], true],
        ['>=', ['coalesce', ['get', 'runup_count'], 0], 100]
      ],
      paint: {
        'circle-radius': kmToPixels(['/', impactRadiusKm, 3]),  // 1/3 of outer
        'circle-color': 'transparent',
        'circle-stroke-color': '#00bcd4',
        'circle-stroke-width': 2.5,
        'circle-stroke-opacity': opacityExpr(0.6),
        'circle-pitch-alignment': 'map'
      }
    });

    // 4. SELECTED EVENT LAYERS - filled circles for clicked event
    map.addLayer({
      id: this._layerId('radius-outer-selected', eventType),
      type: 'circle',
      source: sourceId,
      filter: ['==', ['get', 'event_id'], ''],  // Initially matches nothing
      paint: {
        'circle-radius': kmToPixels(impactRadiusKm),
        'circle-color': '#00bcd4',
        'circle-opacity': 0.12,
        'circle-stroke-color': '#00bcd4',
        'circle-stroke-width': 2,
        'circle-stroke-opacity': 0.5,
        'circle-pitch-alignment': 'map'
      }
    });

    map.addLayer({
      id: this._layerId('radius-inner-selected', eventType),
      type: 'circle',
      source: sourceId,
      filter: ['==', ['get', 'event_id'], ''],
      paint: {
        'circle-radius': kmToPixels(['/', impactRadiusKm, 3]),
        'circle-color': '#00bcd4',
        'circle-opacity': 0.2,
        'circle-stroke-color': '#00bcd4',
        'circle-stroke-width': 3,
        'circle-stroke-opacity': 0.7,
        'circle-pitch-alignment': 'map'
      }
    });

    // 5. WAVE FRONT CIRCLE - tsunami wave expanding to furthest runup location
    // Uses _waveRadiusKm from filterByLifecycle, target = max_runup_dist_km from data
    map.addLayer({
      id: this._layerId('wavefront', eventType),
      type: 'circle',
      source: sourceId,
      filter: ['all',
        ['==', ['geometry-type'], 'Point'],
        ['has', '_waveRadiusKm'],
        ['>', ['get', '_waveRadiusKm'], 0]
      ],
      paint: {
        'circle-radius': kmToPixels(['get', '_waveRadiusKm']),
        'circle-color': 'transparent',
        'circle-stroke-color': '#4dd0e1',  // Teal wave front
        'circle-stroke-width': 3,
        'circle-stroke-opacity': ['*', 0.7, ['coalesce', ['get', '_opacity'], 1.0]],
        'circle-pitch-alignment': 'map'
      }
    });

    // 6. WAVE FRONT GLOW - subtle glow around wave front
    map.addLayer({
      id: this._layerId('wavefront-glow', eventType),
      type: 'circle',
      source: sourceId,
      filter: ['all',
        ['==', ['geometry-type'], 'Point'],
        ['has', '_waveRadiusKm'],
        ['>', ['get', '_waveRadiusKm'], 0]
      ],
      paint: {
        'circle-radius': kmToPixels(['+', ['get', '_waveRadiusKm'], 20]),
        'circle-color': '#4dd0e1',
        'circle-opacity': ['*', 0.08, ['coalesce', ['get', '_opacity'], 1.0]],
        'circle-blur': 0.8,
        'circle-pitch-alignment': 'map'  // Follow globe surface
      }
    });

    // 7. GLOW layer
    map.addLayer({
      id: this._layerId('circle-glow', eventType),
      type: 'circle',
      source: sourceId,
      filter: ['==', ['geometry-type'], 'Point'],
      layout: {
        'circle-sort-key': sortKey
      },
      paint: {
        'circle-radius': sizeBoostExpr(['+', sizeExpr, 4]),
        'circle-color': colorExpr,
        'circle-opacity': opacityExpr(0.14),
        'circle-blur': 0.65
      }
    });

    // 8. MAIN CIRCLE layer
    map.addLayer({
      id: this._layerId('circle', eventType),
      type: 'circle',
      source: sourceId,
      filter: ['==', ['geometry-type'], 'Point'],
      layout: {
        'circle-sort-key': sortKey
      },
      paint: {
        'circle-radius': sizeBoostExpr(sizeExpr),
        'circle-color': colorExpr,
        'circle-opacity': opacityExpr(this._baseCircleOpacity(0.9, eventType)),
        'circle-stroke-color': [
          'case',
          ['==', isSourceExpr, true], '#0d47a1',  // Dark blue stroke for source
          '#1565c0'  // Slightly lighter blue for runups
        ],
        'circle-stroke-width': [
          'case',
          ['==', isSourceExpr, true], this._baseCircleStrokeWidth(2, eventType),  // Thicker stroke for source
          this._baseCircleStrokeWidth(1, eventType)
        ]
      }
    });
  },

  _addTsunamiIconLayer(eventType) {
    const recencyExpr = ['coalesce', ['get', '_recency'], 1.0];
    const lifecycleOpacity = ['coalesce', ['get', '_opacity'], 1.0];
    const isSourceExpr = ['coalesce', ['get', 'is_source'], false];
    const iconSizeExpr = [
      'case',
      ['==', isSourceExpr, true],
      [
        'interpolate', ['linear'],
        ['log10', ['max', 1, ['coalesce', ['get', 'runup_count'], 1]]],
        0, 0.74,
        1, 0.9,
        2, 1.12,
        3.7, 1.34
      ],
      [
        'interpolate', ['linear'],
        ['coalesce', ['get', 'water_height_m'], 1],
        0, 0.64,
        5, 0.8,
        10, 1.0,
        20, 1.22
      ]
    ];
    const iconOpacity = ['min', 1.0, ['*', 0.95, ['*', recencyExpr, lifecycleOpacity]]];
    this._addDisasterIconLayer(eventType, iconSizeExpr, iconOpacity, ['==', ['geometry-type'], 'Point']);
  },

  /**
   * Add wildfire-specific fallback point layer.
   * Polygon wildfire geometry is handled by PolygonModel through the registry.
   * This model only renders point fallback markers when no perimeter geometry
   * is present in the payload.
   * @private
   */
  _addWildfireLayer(eventType, options = {}) {
    const map = MapAdapter.map;
    const sourceId = this._layerId('source', eventType);
    const sortKey = this._getCircleSortKey(eventType);

    // Recency-based effects for animation
    const recencyExpr = ['coalesce', ['get', '_recency'], 1.0];
    const lifecycleOpacity = ['coalesce', ['get', '_opacity'], 1.0];
    const opacityExpr = (baseOpacity) => [
      'min', 1.0,
      ['*', baseOpacity, ['*', recencyExpr, lifecycleOpacity]]
    ];
    const sizeBoostExpr = (baseSize) => ['*', baseSize, ['max', 1.0, recencyExpr]];

    // Color gradient: smaller fires = orange, larger = deep red
    const colorExpr = [
      'interpolate', ['linear'],
      ['log10', ['max', 10, ['coalesce', ['get', 'area_km2'], 100]]],
      2, '#ff8800',    // 100 km2 = orange
      3, '#ff4400',    // 1000 km2 = red-orange
      4, '#cc0000',    // 10000 km2 = red
      4.5, '#880000'   // 30000+ km2 = dark red
    ];

    // Filter for point geometries (fires without perimeters)
    const pointFilter = ['==', ['geometry-type'], 'Point'];

    // Size based on area_km2 (log scale)
    const sizeExpr = [
      'interpolate', ['linear'],
      ['log10', ['max', 10, ['coalesce', ['get', 'area_km2'], 100]]],
      2, 5, 3, 10, 4, 16, 4.5, 22
    ];

    // Outer glow layer (points only)
    map.addLayer({
      id: this._layerId('circle-glow', eventType),
      type: 'circle',
      source: sourceId,
      filter: pointFilter,
      layout: {
        'circle-sort-key': sortKey
      },
      paint: {
        'circle-radius': sizeBoostExpr(['*', sizeExpr, 2]),
        'circle-color': '#ff6600',
        'circle-opacity': opacityExpr(0.25),
        'circle-blur': 1
      }
    });

    map.addLayer({
      id: this._layerId('circle-hit', eventType),
      type: 'circle',
      source: sourceId,
      filter: pointFilter,
      layout: {
        'circle-sort-key': sortKey
      },
      paint: {
        'circle-radius': ['max', 12, sizeBoostExpr(['*', sizeExpr, 2.8])],
        'circle-color': '#ff6600',
        'circle-opacity': 0.01
      }
    });

    // Main fire circle (points only)
    map.addLayer({
      id: this._layerId('circle', eventType),
      type: 'circle',
      source: sourceId,
      filter: pointFilter,
      layout: {
        'circle-sort-key': sortKey
      },
      paint: {
        'circle-radius': sizeBoostExpr(sizeExpr),
        'circle-color': colorExpr,
        'circle-opacity': opacityExpr(this._baseCircleOpacity(0.85, eventType)),
        'circle-stroke-color': '#ffcc00',
        'circle-stroke-width': this._baseCircleStrokeWidth(1.5, eventType)
      }
    });
  },

  _addWildfireIconLayer(eventType) {
    const recencyExpr = ['coalesce', ['get', '_recency'], 1.0];
    const lifecycleOpacity = ['coalesce', ['get', '_opacity'], 1.0];
    const iconSizeExpr = [
      'interpolate', ['linear'],
      ['log10', ['max', 10, ['coalesce', ['get', 'area_km2'], 100]]],
      2, 0.76,
      3, 0.96,
      4, 1.2,
      4.5, 1.38
    ];
    const iconOpacity = ['min', 1.0, ['*', 0.96, ['*', recencyExpr, lifecycleOpacity]]];
    this._addDisasterIconLayer(eventType, iconSizeExpr, iconOpacity, ['==', ['geometry-type'], 'Point']);
  },

  /**
   * Add flood-specific layer.
   * Renders flood events as blue circles sized by affected area.
   * Uses duration for opacity intensity.
   * @private
   */
  _addFloodLayer(eventType, options = {}) {
    const map = MapAdapter.map;
    const sourceId = this._layerId('source', eventType);
    const sortKey = this._getCircleSortKey(eventType);

    // Recency-based effects for animation
    const recencyExpr = ['coalesce', ['get', '_recency'], 1.0];
    const lifecycleOpacity = ['coalesce', ['get', '_opacity'], 1.0];
    const opacityExpr = (baseOpacity) => [
      'min', 1.0,
      ['*', baseOpacity, ['*', recencyExpr, lifecycleOpacity]]
    ];
    const sizeBoostExpr = (baseSize) => ['*', baseSize, ['max', 1.0, recencyExpr]];

    // Color gradient: lighter blue for shorter floods, darker for longer
    const colorExpr = [
      'interpolate', ['linear'],
      ['log10', ['max', 1, ['coalesce', ['get', 'duration_days'], 7]]],
      0, '#66b3ff',    // 1 day = light blue
      1, '#3399ff',    // 10 days = medium blue
      1.5, '#0066cc',  // 30 days = dark blue
      2, '#003366'     // 100+ days = very dark blue
    ];

    // Size based on affected area (use dead_count as proxy for severity, or default)
    const sizeExpr = [
      'interpolate', ['linear'],
      ['log10', ['max', 1, ['coalesce', ['get', 'duration_days'], 7]]],
      0, 6,    // Short floods = small
      1, 10,   // 10 days = medium
      1.5, 14, // 30 days = large
      2, 18    // 100+ days = extra large
    ];

    // Outer glow layer
    map.addLayer({
      id: this._layerId('circle-glow', eventType),
      type: 'circle',
      source: sourceId,
      layout: {
        'circle-sort-key': sortKey
      },
      paint: {
        'circle-radius': sizeBoostExpr(['*', sizeExpr, 1.8]),
        'circle-color': colorExpr,
        'circle-opacity': opacityExpr(0.2),
        'circle-blur': 0.8
      }
    });

    // Main flood circle
    map.addLayer({
      id: this._layerId('circle', eventType),
      type: 'circle',
      source: sourceId,
      layout: {
        'circle-sort-key': sortKey
      },
      paint: {
        'circle-radius': sizeBoostExpr(sizeExpr),
        'circle-color': colorExpr,
        'circle-opacity': opacityExpr(this._baseCircleOpacity(0.75, eventType)),
        'circle-stroke-color': '#003366',
        'circle-stroke-width': this._baseCircleStrokeWidth(1.5, eventType)
      }
    });
  },

  _addFloodIconLayer(eventType) {
    const recencyExpr = ['coalesce', ['get', '_recency'], 1.0];
    const lifecycleOpacity = ['coalesce', ['get', '_opacity'], 1.0];
    const iconSizeExpr = [
      'interpolate', ['linear'],
      ['log10', ['max', 1, ['coalesce', ['get', 'duration_days'], 7]]],
      0, 0.7,
      1, 0.9,
      1.5, 1.12,
      2, 1.28
    ];
    const iconOpacity = ['min', 1.0, ['*', 0.95, ['*', recencyExpr, lifecycleOpacity]]];
    this._addDisasterIconLayer(eventType, iconSizeExpr, iconOpacity, ['==', ['geometry-type'], 'Point']);
  },

  /**
   * Add tornado-specific layers.
   * Uses EF/F scale for color, damage_radius_km for impact zone.
   * Supports drill-down to show track line when clicked.
   * @private
   */
  _addTornadoLayer(eventType, options = {}) {
    const map = MapAdapter.map;
    const sourceId = this._layerId('source', eventType);
    const sortKey = this._getCircleSortKey(eventType);

    // Recency-based effects for animation
    const recencyExpr = ['coalesce', ['get', '_recency'], 1.0];
    const lifecycleOpacity = ['coalesce', ['get', '_opacity'], 1.0];
    const opacityExpr = (baseOpacity) => [
      'min', 1.0,
      ['*', baseOpacity, ['*', recencyExpr, lifecycleOpacity]]
    ];
    const sizeBoostExpr = (baseSize) => ['*', baseSize, ['max', 1.0, recencyExpr]];

    // Color by tornado scale (EF0-EF5 or legacy F0-F5)
    // Maps to severe weather convention: green to red
    // tornado_scale can be "EF0", "F3", etc. - extract number
    const scaleNumExpr = [
      'to-number',
      ['slice', ['coalesce', ['get', 'tornado_scale'], 'EF0'], -1],
      0
    ];

    const colorExpr = [
      'interpolate', ['linear'], scaleNumExpr,
      0, '#98fb98',  // EF0 - Pale green (weak)
      1, '#32cd32',  // EF1 - Lime green
      2, '#ffd700',  // EF2 - Gold (significant)
      3, '#ff8c00',  // EF3 - Dark orange (severe)
      4, '#ff4500',  // EF4 - Orange-red (devastating)
      5, '#8b0000'   // EF5 - Dark red (violent)
    ];

    // Size by EF scale - larger = stronger tornado
    const sizeExpr = [
      'interpolate', ['linear'], scaleNumExpr,
      0, 4,   // EF0 = 4px
      1, 6,   // EF1 = 6px
      2, 8,   // EF2 = 8px
      3, 10,  // EF3 = 10px
      4, 13,  // EF4 = 13px
      5, 16   // EF5 = 16px
    ];

    // Helper: convert km to pixels at current zoom
    const kmToPixels = (kmExpr) => [
      'interpolate', ['exponential', 2], ['zoom'],
      0, ['/', kmExpr, 156.5],
      5, ['/', kmExpr, 4.9],
      10, ['*', kmExpr, 6.54],
      15, ['*', kmExpr, 209]
    ];

    // 1. FELT RADIUS - shows broader impact zone for visibility on map
    // Uses felt_radius_km (larger) so tornadoes are easier to find
    map.addLayer({
      id: this._layerId('radius-outer', eventType),
      type: 'circle',
      source: sourceId,
      filter: ['>', ['coalesce', ['get', 'felt_radius_km'], 0], 0],
      paint: {
        'circle-radius': kmToPixels(['get', 'felt_radius_km']),
        'circle-color': 'transparent',
        'circle-stroke-color': colorExpr,
        'circle-stroke-width': 1.5,
        'circle-stroke-opacity': opacityExpr(0.3)
      }
    });

    // 2. SELECTED EVENT LAYERS - show both radii for clicked event
    // 2a. FELT RADIUS (outer) - broader impact zone
    map.addLayer({
      id: this._layerId('radius-outer-selected-felt', eventType),
      type: 'circle',
      source: sourceId,
      filter: ['==', ['get', 'event_id'], ''],  // Initially matches nothing
      paint: {
        'circle-radius': kmToPixels(['coalesce', ['get', 'felt_radius_km'], 0.1]),
        'circle-color': colorExpr,
        'circle-opacity': 0.15,
        'circle-stroke-color': colorExpr,
        'circle-stroke-width': 1.5,
        'circle-stroke-opacity': 0.5
      }
    });

    // 2b. DAMAGE RADIUS (inner) - actual tornado width
    map.addLayer({
      id: this._layerId('radius-outer-selected', eventType),
      type: 'circle',
      source: sourceId,
      filter: ['==', ['get', 'event_id'], ''],  // Initially matches nothing
      paint: {
        'circle-radius': kmToPixels(['coalesce', ['get', 'damage_radius_km'], 0.05]),
        'circle-color': colorExpr,
        'circle-opacity': 0.3,
        'circle-stroke-color': colorExpr,
        'circle-stroke-width': 2,
        'circle-stroke-opacity': 0.8
      }
    });

    // 3. TORNADO TRACK LINE - shown during drill-down
    // Uses separate source added by drill-down handler
    // This layer is just a placeholder - actual track uses tornado-track source

    // 4. GLOW layer
    map.addLayer({
      id: this._layerId('circle-glow', eventType),
      type: 'circle',
      source: sourceId,
      layout: {
        'circle-sort-key': sortKey
      },
      paint: {
        'circle-radius': sizeBoostExpr(['+', sizeExpr, 4]),
        'circle-color': colorExpr,
        'circle-opacity': opacityExpr(0.35),
        'circle-blur': 1
      }
    });

    // 5. MAIN TORNADO MARKER
    map.addLayer({
      id: this._layerId('circle', eventType),
      type: 'circle',
      source: sourceId,
      layout: {
        'circle-sort-key': sortKey
      },
      paint: {
        'circle-radius': sizeBoostExpr(sizeExpr),
        'circle-color': colorExpr,
        'circle-opacity': opacityExpr(this._baseCircleOpacity(0.9, eventType)),
        'circle-stroke-color': '#222222',
        'circle-stroke-width': this._baseCircleStrokeWidth(1, eventType)
      }
    });
  },

  _addTornadoIconLayer(eventType) {
    const recencyExpr = ['coalesce', ['get', '_recency'], 1.0];
    const lifecycleOpacity = ['coalesce', ['get', '_opacity'], 1.0];
    const scaleNumExpr = [
      'to-number',
      ['slice', ['coalesce', ['get', 'tornado_scale'], 'EF0'], -1],
      0
    ];
    const iconSizeExpr = [
      'interpolate', ['linear'], scaleNumExpr,
      0, 0.68,
      1, 0.82,
      2, 0.98,
      3, 1.12,
      4, 1.28,
      5, 1.44
    ];
    const iconOpacity = ['min', 1.0, ['*', 0.97, ['*', recencyExpr, lifecycleOpacity]]];
    this._addDisasterIconLayer(eventType, iconSizeExpr, iconOpacity);
  },

  /**
   * Add landslide layer - brown points scaled by intensity (deaths).
   * @private
   */
  _addLandslideLayer(eventType, options = {}) {
    const map = MapAdapter.map;
    const sourceId = this._layerId('source', eventType);
    const sortKey = this._getCircleSortKey(eventType);

    // Recency-based effects for animation
    const recencyExpr = ['coalesce', ['get', '_recency'], 1.0];
    const lifecycleOpacity = ['coalesce', ['get', '_opacity'], 1.0];
    const opacityExpr = (baseOpacity) => [
      'min', 1.0,
      ['*', baseOpacity, ['*', recencyExpr, lifecycleOpacity]]
    ];
    const sizeBoostExpr = (baseSize) => ['*', baseSize, ['max', 1.0, recencyExpr]];

    // Color gradient: lighter brown for less intense, darker for more deaths
    const colorExpr = [
      'interpolate', ['linear'],
      ['coalesce', ['get', 'intensity'], 1],
      1, '#cd853f',    // Low intensity = peru/tan
      2, '#a0522d',    // Moderate = sienna
      3, '#8b4513',    // High = saddle brown
      4, '#654321',    // Very high = dark brown
      5, '#3d2314'     // Extreme = very dark brown
    ];

    // Size based on intensity (deaths-based, calculated in backend)
    const sizeExpr = [
      'interpolate', ['linear'],
      ['coalesce', ['get', 'intensity'], 1],
      1, 6,    // Low intensity = small
      2, 8,    // Moderate
      3, 11,   // High
      4, 14,   // Very high
      5, 18    // Extreme
    ];

    // Outer glow layer
    map.addLayer({
      id: this._layerId('circle-glow', eventType),
      type: 'circle',
      source: sourceId,
      layout: {
        'circle-sort-key': sortKey
      },
      paint: {
        'circle-radius': sizeBoostExpr(['*', sizeExpr, 1.8]),
        'circle-color': colorExpr,
        'circle-opacity': opacityExpr(0.25),
        'circle-blur': 0.8
      }
    });

    // Main landslide circle
    map.addLayer({
      id: this._layerId('circle', eventType),
      type: 'circle',
      source: sourceId,
      layout: {
        'circle-sort-key': sortKey
      },
      paint: {
        'circle-radius': sizeBoostExpr(sizeExpr),
        'circle-color': colorExpr,
        'circle-opacity': opacityExpr(this._baseCircleOpacity(0.9, eventType)),
        'circle-stroke-color': '#222222',
        'circle-stroke-width': this._baseCircleStrokeWidth(1, eventType)
      }
    });
  },

  _addLandslideIconLayer(eventType) {
    const recencyExpr = ['coalesce', ['get', '_recency'], 1.0];
    const lifecycleOpacity = ['coalesce', ['get', '_opacity'], 1.0];
    const iconSizeExpr = [
      'interpolate', ['linear'],
      ['coalesce', ['get', 'intensity'], 1],
      1, 0.72,
      2, 0.88,
      3, 1.04,
      4, 1.22,
      5, 1.36
    ];
    const iconOpacity = ['min', 1.0, ['*', 0.95, ['*', recencyExpr, lifecycleOpacity]]];
    this._addDisasterIconLayer(eventType, iconSizeExpr, iconOpacity);
  },

  /**
   * Add generic event layer for other event types.
   * @private
   */
  _addGenericEventLayer(eventType, options = {}) {
    const map = MapAdapter.map;
    const sourceId = this._layerId('source', eventType);
    const sortKey = this._getCircleSortKey(eventType);

    // Recency-based effects for animation
    // _recency: 1.5 = brand new (flash), 1.0 = recent, 0.0 = fading out
    const recencyExpr = ['coalesce', ['get', '_recency'], 1.0];
    const lifecycleOpacity = ['coalesce', ['get', '_opacity'], 1.0];
    const opacityExpr = (baseOpacity) => [
      'min', 1.0,
      ['*', baseOpacity, ['*', recencyExpr, lifecycleOpacity]]
    ];
    const sizeBoostExpr = (baseSize) => ['*', baseSize, ['max', 1.0, recencyExpr]];

    // Default yellow/orange coloring
    map.addLayer({
      id: this._layerId('circle-glow', eventType),
      type: 'circle',
      source: sourceId,
      layout: {
        'circle-sort-key': sortKey
      },
      paint: {
        'circle-radius': sizeBoostExpr(12),
        'circle-color': '#ffcc00',
        'circle-opacity': opacityExpr(0.3),  // Fade with recency, cap at 1.0
        'circle-blur': 1
      }
    });

    map.addLayer({
      id: this._layerId('circle', eventType),
      type: 'circle',
      source: sourceId,
      layout: {
        'circle-sort-key': sortKey
      },
      paint: {
        'circle-radius': sizeBoostExpr(6),
        'circle-color': '#ffcc00',
        'circle-opacity': opacityExpr(0.85),  // Fade with recency, cap at 1.0
        'circle-stroke-color': '#333333',
        'circle-stroke-width': 1
      }
    });
  },

  /**
   * Update existing source data or create layers if needed.
   * Used for time-based filtering and animation updates.
   * @param {Object} geojson - GeoJSON FeatureCollection
   * @param {Object} options - Options including eventType for layer creation
   */
  update(geojson, options = {}) {
    if (!MapAdapter?.map) return;

    // Determine event type from options or fall back to first active type
    const eventType = options.eventType || this.activeType || 'generic_event';
    const sourceId = this._layerId('source', eventType);
    const source = MapAdapter.map.getSource(sourceId);
    const sortedGeojson = this._sortGeojsonForEventType(geojson, eventType);
    if (source) {
      source.setData(sortedGeojson);
    } else {
      // Source doesn't exist, need to render with proper event type
      this.render(sortedGeojson, eventType, options);
    }
  },

  /**
   * Handle sequence animation request from central dispatcher.
   * Called by ModelRegistry when disaster-sequence-request event fires.
   * @param {string} eventId - Event ID
   * @param {string} eventType - Event type (earthquake, tsunami, wildfire, flood, tornado)
   * @param {Object} props - Event properties from the clicked feature
   */
  async handleSequence(eventId, eventType, props) {
    const model = this;

    switch (eventType) {
      case 'earthquake':
        if (props.sequence_id || eventId) {
          model._notifySequenceChange(props.sequence_id, eventId);
        }
        break;

      case 'tsunami':
        if (eventId) {
          try {
            const url = `/api/tsunamis/${eventId}/animation`;
            const data = await fetchMsgpack(url);
            if (data.features && data.features.length > 1) {
              model._notifyTsunamiRunups(data, eventId);
            }
          } catch (err) {
            console.error('Error fetching tsunami runups:', err);
          }
        }
        break;

      case 'wildfire':
        if (props.event_id) {
          const year = props.year || (props.timestamp ? new Date(props.timestamp).getFullYear() : null);

          // Option 1: Try progression data (daily snapshots)
          if (props.has_progression) {
            try {
              const url = year
                ? `/api/wildfires/${props.event_id}/progression?year=${year}`
                : `/api/wildfires/${props.event_id}/progression`;
              const data = await fetchMsgpack(url);

              let snapshots, totalDays;
              if (data.type === 'FeatureCollection' && data.features) {
                snapshots = data.features.map(f => ({
                  date: f.properties.date,
                  day_num: f.properties.day_num,
                  area_km2: f.properties.area_km2,
                  geometry: f.geometry
                }));
                totalDays = data.metadata?.total_count || snapshots.length;
              } else {
                snapshots = data.snapshots;
                totalDays = data.total_days;
              }

              if (snapshots && snapshots.length > 0) {
                const normalizedData = { snapshots, total_days: totalDays };
                model._notifyFireProgression(normalizedData, props.event_id, props.timestamp, props.latitude, props.longitude);
                break;
              }
            } catch (err) {
              console.error('Error fetching fire progression:', err);
            }
          }

          // Option 2: Try perimeter data (final shape)
          try {
            const perimUrl = year
              ? `/api/wildfires/${props.event_id}/perimeter?year=${year}`
              : `/api/wildfires/${props.event_id}/perimeter`;
            const perimData = await fetchMsgpack(perimUrl);
            if (perimData.type === 'Feature' && perimData.geometry) {
              model._notifyWildfirePerimeter({
                eventId: props.event_id,
                fireName: props.fire_name || 'Wildfire',
                geometry: perimData,
                latitude: props.latitude,
                longitude: props.longitude,
                areaKm2: props.area_km2,
                timestamp: props.timestamp
              });
              break;
            }
          } catch (err) {
            console.log('No perimeter data, falling back to circle');
          }

          // Option 3: Fallback to area circle
          if (props.latitude && props.longitude && props.area_km2 > 0) {
            const radiusKm = Math.sqrt(props.area_km2 / Math.PI);
            model._notifyWildfireImpact({
              eventId: props.event_id,
              fireName: props.fire_name || 'Wildfire',
              latitude: props.latitude,
              longitude: props.longitude,
              areaKm2: props.area_km2,
              radiusKm: radiusKm,
              timestamp: props.timestamp
            });
          }
        }
        break;

      case 'flood':
        if (props.event_id) {
          // Try to get geometry data first
          if (props.has_geometry) {
            try {
              const url = `/api/floods/${props.event_id}/geometry`;
              const data = await fetchMsgpack(url);
              // Handle both Feature (single geometry) and FeatureCollection formats
              if (data.type === 'Feature' && data.geometry) {
                model._notifyFloodAnimation(data, props.event_id, props.duration_days,
                  props.timestamp, props.end_timestamp, props.latitude, props.longitude, props.event_name);
                break;
              } else if (data.type === 'FeatureCollection' && data.features) {
                model._notifyFloodAnimation(data, props.event_id, props.duration_days,
                  props.timestamp, props.end_timestamp, props.latitude, props.longitude, props.event_name);
                break;
              }
            } catch (err) {
              console.error('Error fetching flood geometry:', err);
            }
          }
          // Fallback: show area circle based on area_km2
          if (props.latitude && props.longitude && props.area_km2 > 0) {
            const radiusKm = Math.sqrt(props.area_km2 / Math.PI); // Circle radius from area
            model._notifyFloodImpact({
              eventId: props.event_id,
              eventName: props.event_name || 'Flood',
              latitude: props.latitude,
              longitude: props.longitude,
              areaKm2: props.area_km2,
              radiusKm: radiusKm,
              durationDays: props.duration_days,
              timestamp: props.timestamp
            });
          }
        }
        break;

      case 'tornado':
        if (props.event_id) {
          try {
            const url = `/api/tornadoes/${props.event_id}/sequence`;
            const data = await fetchMsgpack(url);

            if (data.features && data.features.length > 0) {
              model._notifyTornadoSequence(data, props.event_id);
            } else {
              const hasTrack = props.end_latitude != null || props.end_lat != null;
              if (!hasTrack && props.latitude && props.longitude) {
                model._notifyTornadoPointAnimation(props.event_id, props.latitude, props.longitude,
                  props.tornado_scale, props.timestamp);
              }
            }
          } catch (err) {
            console.error('Error fetching tornado sequence:', err);
            if (props.latitude && props.longitude) {
              model._notifyTornadoPointAnimation(props.event_id, props.latitude, props.longitude,
                props.tornado_scale, props.timestamp);
            }
          }
        }
        break;

      case 'volcano':
        // Show impact radius animation and/or linked earthquakes
        console.log('PointRadiusModel: Volcano impact sequence for', eventId);

        const feltRadius = props.felt_radius_km;
        const damageRadius = props.damage_radius_km;
        const lat = props.latitude;
        const lon = props.longitude;
        const volcanoName = props.volcano_name || 'Volcano';

        if (feltRadius > 0 || damageRadius > 0) {
          // Notify about volcano impact for radius animation
          model._notifyVolcanoImpact({
            eventId,
            volcanoName,
            latitude: lat,
            longitude: lon,
            feltRadius: feltRadius || 0,
            damageRadius: damageRadius || 0,
            VEI: props.VEI,
            timestamp: props.timestamp
          });
        }

        // Also check for linked earthquakes
        if (props.earthquake_event_ids) {
          console.log('Volcano has linked earthquakes:', props.earthquake_event_ids);
        }
        break;

      default:
        console.warn(`PointRadiusModel: Unhandled sequence type: ${eventType}`);
    }
  },

  /**
   * Clear layers for a specific event type only.
   * Allows multiple overlays to coexist without interfering.
   * @param {string} eventType - Event type to clear (e.g., 'earthquake', 'volcano')
   */
  clearType(eventType) {
    if (!MapAdapter?.map || !eventType) return;

    const map = MapAdapter.map;

    // Remove click handler for this type
    const handler = this.clickHandlers.get(eventType);
    if (handler) {
      const circleLayerId = this._layerId('circle', eventType);
      const glowLayerId = this._layerId('circle-glow', eventType);
      const fillLayerId = this._layerId('circle-fill', eventType);
      const hitLayerId = this._layerId('circle-hit', eventType);
      const iconLayerId = this._iconLayerId(eventType);
      map.off('click', circleLayerId, handler);
      map.off('click', glowLayerId, handler);
      map.off('click', fillLayerId, handler);
      map.off('click', hitLayerId, handler);
      map.off('click', iconLayerId, handler);
      this.clickHandlers.delete(eventType);
    }

    // Build list of type-specific layer IDs to remove
    const layerIds = [
      this._layerId('circle', eventType),
      this._layerId('circle-glow', eventType),
      this._layerId('circle-hit', eventType),
      this._iconLayerId(eventType),
      this._layerId('circle-fill', eventType),     // Legacy inline polygon fill
      this._layerId('circle-stroke', eventType),   // Legacy inline polygon stroke
      this._layerId('circle-sequence', eventType), // Green sequence highlight
      this._layerId('label', eventType),
      this._layerId('radius-outer', eventType),
      this._layerId('radius-inner', eventType),
      this._layerId('radius-outer-selected', eventType),
      this._layerId('radius-inner-selected', eventType),
      this._layerId('radius-outer-selected-felt', eventType), // Tornado felt radius selected
      this._layerId('connections', eventType),     // Tsunami connection lines
      this._layerId('wavefront', eventType),       // Tsunami wave front
      this._layerId('wavefront-glow', eventType)   // Wave front glow
    ];

    for (const layerId of layerIds) {
      if (map.getLayer(layerId)) {
        map.removeLayer(layerId);
      }
    }

    // Remove type-specific source
    const sourceId = this._layerId('source', eventType);
    if (map.getSource(sourceId)) {
      map.removeSource(sourceId);
    }

    // Remove from active types
    this.activeTypes.delete(eventType);

    // Clear selection if it was this type
    if (this.selectedEventType === eventType) {
      this.selectedEventId = null;
      this.selectedEventType = null;
    }

    // Clear sequence if it was this type
    if (eventType === 'earthquake') {
      this.activeSequenceId = null;
    }

    // Type-specific cleanup
    if (eventType === 'tsunami') {
      this._inRunupsMode = false;
      this._originalTsunamiData = null;
      this._hideRunupsExitControl();
    }
    if (eventType === 'tornado') {
      this._clearTornadoTrack();
      this._inTrackMode = false;
      this._hideTrackExitControl();
    }
  },

  /**
   * Clear all event layers for all types.
   */
  clear() {
    if (!MapAdapter?.map) return;

    // Clear each active type
    for (const eventType of [...this.activeTypes]) {
      this.clearType(eventType);
    }

    // Remove global map click handler
    if (this._mapClickHandler) {
      MapAdapter.map.off('click', this._mapClickHandler);
      this._mapClickHandler = null;
    }

    // Unlock popup
    MapAdapter.popupLocked = false;

    // Clear all tracking state
    this.activeTypes.clear();
    this.clickHandlers.clear();
    this.selectedEventId = null;
    this.selectedEventType = null;
    this.activeSequenceId = null;
  },

  /**
   * Select an event to highlight with filled radius circles.
   * @param {string|null} eventId - Event ID to select, or null to deselect
   * @param {string} eventType - Event type for layer ID resolution (optional, uses selectedEventType if not provided)
   * @private
   */
  _selectEvent(eventId, eventType = null) {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;
    this.selectedEventId = eventId;

    // Use provided type, or fall back to tracked selected type, or iterate all active types
    const typesToUpdate = eventType
      ? [eventType]
      : (this.selectedEventType ? [this.selectedEventType] : Array.from(this.activeTypes));

    // Update filters on selection layers
    const filter = eventId
      ? ['==', ['get', 'event_id'], eventId]
      : ['==', ['get', 'event_id'], ''];  // Matches nothing

    // Update selection layers for each active type
    for (const type of typesToUpdate) {
      const outerLayer = this._layerId('radius-outer-selected', type);
      const innerLayer = this._layerId('radius-inner-selected', type);
      const feltLayer = this._layerId('radius-outer-selected-felt', type);

      if (map.getLayer(outerLayer)) {
        map.setFilter(outerLayer, filter);
      }
      if (map.getLayer(innerLayer)) {
        map.setFilter(innerLayer, filter);
      }
      if (map.getLayer(feltLayer)) {
        map.setFilter(feltLayer, filter);
      }
    }
  },

  /**
   * Highlight an aftershock sequence on the map.
   * Shows all events in the sequence with enhanced visibility.
   * @param {string|null} sequenceId - Sequence ID to highlight, or null to clear
   * @param {string} eventType - Event type (defaults to 'earthquake' since sequences are earthquake-specific)
   */
  highlightSequence(sequenceId, eventType = 'earthquake') {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;
    const prevSequence = this.activeSequenceId;
    this.activeSequenceId = sequenceId;

    const sourceId = this._layerId('source', eventType);
    const circleLayerId = this._layerId('circle', eventType);

    // Add sequence highlight layer if it doesn't exist
    const seqLayerId = this._layerId('circle-sequence', eventType);
    if (!map.getLayer(seqLayerId) && map.getSource(sourceId)) {
      // Add a highlight ring around sequence events
      map.addLayer({
        id: seqLayerId,
        type: 'circle',
        source: sourceId,
        filter: ['==', ['get', 'sequence_id'], ''],  // Initially matches nothing
        paint: {
          'circle-radius': [
            'interpolate', ['linear'], ['get', 'magnitude'],
            3.0, 8,
            5.0, 12,
            7.0, 18,
            9.0, 24
          ],
          'circle-color': 'transparent',
          'circle-stroke-color': '#76ff03',  // Bright green highlight
          'circle-stroke-width': 3,
          'circle-stroke-opacity': 0.9
        }
      }, circleLayerId);  // Place below epicenters
    }

    // Update filter
    if (map.getLayer(seqLayerId)) {
      const filter = sequenceId
        ? ['==', ['get', 'sequence_id'], sequenceId]
        : ['==', ['get', 'sequence_id'], ''];
      map.setFilter(seqLayerId, filter);
    }

    // Notify callback if sequence changed
    if (this.sequenceChangeCallback && sequenceId !== prevSequence) {
      this.sequenceChangeCallback(sequenceId);
    }

    if (sequenceId) {
      console.log(`PointRadiusModel: Highlighting sequence ${sequenceId}`);
    }
  },

  /**
   * Set callback for sequence changes (used by TimeSlider integration).
   * @param {Function} callback - Called with (sequenceId, eventId) when sequence changes
   */
  onSequenceChange(callback) {
    this.sequenceChangeCallback = callback;
  },

  /**
   * Notify sequence change listeners without highlighting.
   * Used when starting animation - SequenceAnimator handles display.
   * @param {string} sequenceId - Sequence ID
   * @param {string} eventId - Event ID (mainshock ID for accurate aftershock query)
   * @private
   */
  _notifySequenceChange(sequenceId, eventId = null) {
    if (this.sequenceChangeCallback) {
      this.sequenceChangeCallback(sequenceId, eventId);
    }
  },

  /**
   * Notify about earthquakes found near a volcano.
   * @param {Array} features - Earthquake features from API
   * @param {string} volcanoSeqId - Generated sequence ID for this volcano's earthquakes
   * @param {string} volcanoName - Name of the volcano
   * @param {number} lat - Volcano latitude
   * @param {number} lon - Volcano longitude
   */
  _notifyVolcanoEarthquakes(features, volcanoSeqId, volcanoName, lat, lon) {
    console.log(`PointRadiusModel: Found ${features.length} earthquakes near ${volcanoName}`);

    if (this.volcanoEarthquakesCallback) {
      this.volcanoEarthquakesCallback({
        features,
        volcanoSeqId,
        volcanoName,
        volcanoLat: lat,
        volcanoLon: lon
      });
    }
  },

  /**
   * Notify about volcanoes found near an earthquake.
   * @param {Array} features - Volcano features from API
   * @param {number} lat - Earthquake latitude
   * @param {number} lon - Earthquake longitude
   */
  _notifyNearbyVolcanoes(features, lat, lon) {
    console.log(`PointRadiusModel: Found ${features.length} volcanoes near (${lat}, ${lon})`);

    if (this.nearbyVolcanoesCallback) {
      this.nearbyVolcanoesCallback({
        features,
        earthquakeLat: lat,
        earthquakeLon: lon
      });
    }
  },

  _notifyRelatedChain(data) {
    const count = Math.max(0, (data?.features?.length || 1) - 1);
    console.log(`PointRadiusModel: Loaded linked disaster chain with ${count} related events`);

    if (this.relatedChainCallback) {
      this.relatedChainCallback(data);
    } else {
      console.warn('PointRadiusModel: No related chain callback registered');
    }
  },

  _notifyVolcanoHistory(features, volcanoName, lat, lon, radiusKm = 20) {
    console.log(`PointRadiusModel: Found ${features.length} historical eruptions near ${volcanoName}`);

    if (this.volcanoHistoryCallback) {
      this.volcanoHistoryCallback({
        features,
        volcanoName,
        volcanoLat: lat,
        volcanoLon: lon,
        radiusKm
      });
    }
  },

  /**
   * Register callback for volcano-triggered earthquakes.
   * @param {Function} callback - Callback function
   */
  onVolcanoEarthquakes(callback) {
    this.volcanoEarthquakesCallback = callback;
  },

  /**
   * Register callback for nearby volcanoes.
   * @param {Function} callback - Callback function
   */
  onNearbyVolcanoes(callback) {
    this.nearbyVolcanoesCallback = callback;
  },

  onVolcanoHistory(callback) {
    this.volcanoHistoryCallback = callback;
  },

  onRelatedChain(callback) {
    this.relatedChainCallback = callback;
  },

  /**
   * Register callback for volcano impact animation.
   * @param {Function} callback - Callback function receiving {eventId, volcanoName, latitude, longitude, feltRadius, damageRadius, VEI, timestamp}
   */
  onVolcanoImpact(callback) {
    this.volcanoImpactCallback = callback;
  },

  /**
   * Notify about volcano impact for radius animation.
   * @param {Object} data - Impact data
   */
  _notifyVolcanoImpact(data) {
    console.log(`PointRadiusModel: Volcano impact animation for ${data.volcanoName} (felt: ${data.feltRadius}km, damage: ${data.damageRadius}km)`);

    if (this.volcanoImpactCallback) {
      this.volcanoImpactCallback(data);
    } else {
      console.warn('PointRadiusModel: No volcano impact callback registered');
    }
  },

  /**
   * Register callback for wildfire impact animation (area circle fallback).
   * @param {Function} callback - Callback function
   */
  onWildfireImpact(callback) {
    this.wildfireImpactCallback = callback;
  },

  /**
   * Notify about wildfire impact for area circle animation.
   * @param {Object} data - Impact data {eventId, fireName, latitude, longitude, areaKm2, radiusKm, timestamp}
   */
  _notifyWildfireImpact(data) {
    console.log(`PointRadiusModel: Wildfire impact animation for ${data.fireName} (${data.areaKm2} km2)`);

    if (this.wildfireImpactCallback) {
      this.wildfireImpactCallback(data);
    } else {
      console.warn('PointRadiusModel: No wildfire impact callback registered');
    }
  },

  /**
   * Register callback for wildfire perimeter animation (fade-in shape).
   * @param {Function} callback - Callback function
   */
  onWildfirePerimeter(callback) {
    this.wildfirePerimeterCallback = callback;
  },

  /**
   * Notify about wildfire perimeter for fade-in animation.
   * @param {Object} data - Perimeter data {eventId, fireName, geometry, latitude, longitude, areaKm2, timestamp}
   */
  _notifyWildfirePerimeter(data) {
    console.log(`PointRadiusModel: Wildfire perimeter animation for ${data.fireName}`);

    if (this.wildfirePerimeterCallback) {
      this.wildfirePerimeterCallback(data);
    } else {
      console.warn('PointRadiusModel: No wildfire perimeter callback registered');
    }
  },

  /**
   * Register callback for flood impact animation (area circle fallback).
   * @param {Function} callback - Callback function
   */
  onFloodImpact(callback) {
    this.floodImpactCallback = callback;
  },

  /**
   * Notify about flood impact for area circle animation.
   * @param {Object} data - Impact data {eventId, eventName, latitude, longitude, areaKm2, radiusKm, durationDays, timestamp}
   */
  _notifyFloodImpact(data) {
    console.log(`PointRadiusModel: Flood impact animation for ${data.eventName} (${data.areaKm2} km2)`);

    if (this.floodImpactCallback) {
      this.floodImpactCallback(data);
    } else {
      console.warn('PointRadiusModel: No flood impact callback registered');
    }
  },

  /**
   * Notify about tsunami runups loaded for an event.
   * @param {Object} data - GeoJSON with source + runups from animation endpoint
   * @param {string} eventId - Tsunami event ID
   */
  _notifyTsunamiRunups(data, eventId) {
    console.log(`PointRadiusModel: Loaded ${data.features?.length - 1 || 0} runups for ${eventId}`);

    if (this.tsunamiRunupsCallback) {
      this.tsunamiRunupsCallback({
        geojson: data,
        eventId: eventId,
        runupCount: data.metadata?.runup_count || 0
      });
    } else {
      // Default behavior: update the map source directly with combined data
      this._displayTsunamiRunups(data);
    }
  },

  /**
   * Display tsunami runups on the map (default behavior).
   * Stores original data so user can exit back to normal view.
   * @param {Object} geojson - GeoJSON with source + runups
   */
  _displayTsunamiRunups(geojson) {
    if (!MapAdapter?.map) return;

    const sourceId = this._layerId('source', 'tsunami');
    const source = MapAdapter.map.getSource(sourceId);
    if (source) {
      // Store original data if not already in runups mode
      if (!this._inRunupsMode && source._data) {
        this._originalTsunamiData = source._data;
        this._inRunupsMode = true;
      }

      // Update the source data with combined features
      source.setData(geojson);

      // Fit bounds to show all points
      this.fitBounds(geojson);

      // Show exit button in popup or add to map
      this._showRunupsExitControl();

      console.log(`PointRadiusModel: Displaying ${geojson.features?.length || 0} tsunami features (runups mode)`);
    }
  },

  /**
   * Display a tornado track on the map.
   * Shows track line, start point, end point, and impact radius.
   * @param {Object} data - Tornado detail data with track GeoJSON
   */
  _displayTornadoTrack(data) {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;
    const trackSourceId = 'tornado-track';
    const trackLayerId = 'tornado-track-line';
    const pointsLayerId = 'tornado-track-points';
    const radiusLayerId = 'tornado-track-radius';

    // Clean up any existing track layers
    this._clearTornadoTrack();

    // Get scale color for consistent styling
    const scale = data.tornado_scale || 'EF0';
    const scaleColors = {
      'EF0': '#98fb98', 'F0': '#98fb98',
      'EF1': '#32cd32', 'F1': '#32cd32',
      'EF2': '#ffd700', 'F2': '#ffd700',
      'EF3': '#ff8c00', 'F3': '#ff8c00',
      'EF4': '#ff4500', 'F4': '#ff4500',
      'EF5': '#8b0000', 'F5': '#8b0000'
    };
    const trackColor = scaleColors[scale] || '#32cd32';

    // Build GeoJSON with track line and endpoint markers
    const features = [];

    // Add track line if available
    if (data.track && data.track.geometry) {
      features.push({
        type: 'Feature',
        geometry: data.track.geometry,
        properties: { type: 'track', tornado_scale: scale }
      });
    }

    // Add start point marker
    if (data.latitude != null && data.longitude != null) {
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [data.longitude, data.latitude] },
        properties: { type: 'start', tornado_scale: scale, label: 'START' }
      });
    }

    // Add end point marker
    if (data.end_latitude != null && data.end_longitude != null) {
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [data.end_longitude, data.end_latitude] },
        properties: { type: 'end', tornado_scale: scale, label: 'END' }
      });
    }

    const geojson = { type: 'FeatureCollection', features };

    // Add source
    map.addSource(trackSourceId, { type: 'geojson', data: geojson });

    // Helper: km to pixels
    const kmToPixels = (km) => [
      'interpolate', ['exponential', 2], ['zoom'],
      0, km / 156.5,
      5, km / 4.9,
      10, km * 6.54,
      15, km * 209
    ];

    // Add impact radius along track (using damage_radius_km from parquet)
    if (data.damage_radius_km > 0) {
      map.addLayer({
        id: radiusLayerId,
        type: 'line',
        source: trackSourceId,
        filter: ['==', ['get', 'type'], 'track'],
        paint: {
          'line-color': trackColor,
          'line-width': kmToPixels(data.damage_radius_km * 2),
          'line-opacity': 0.25
        }
      });
    }

    // Add track line layer
    map.addLayer({
      id: trackLayerId,
      type: 'line',
      source: trackSourceId,
      filter: ['==', ['get', 'type'], 'track'],
      paint: {
        'line-color': trackColor,
        'line-width': 4,
        'line-opacity': 0.9
      }
    });

    // Add endpoint markers
    map.addLayer({
      id: pointsLayerId,
      type: 'circle',
      source: trackSourceId,
      filter: ['in', ['get', 'type'], ['literal', ['start', 'end']]],
      paint: {
        'circle-radius': 8,
        'circle-color': [
          'case',
          ['==', ['get', 'type'], 'start'], '#00ff00',  // Green for start
          '#ff0000'  // Red for end
        ],
        'circle-stroke-color': '#222',
        'circle-stroke-width': 2
      }
    });

    // Fit map to track bounds
    if (data.track?.geometry?.coordinates?.length > 0) {
      const bounds = new maplibregl.LngLatBounds();
      extendBoundsWithCoordinateList(bounds, data.track.geometry.coordinates);
      map.fitBounds(bounds, { padding: 80, duration: 800, maxZoom: 12 });
    }

    // Show exit control
    this._showTrackExitControl();
    this._inTrackMode = true;

    console.log(`PointRadiusModel: Displaying tornado track for ${data.event_id}`);
  },

  /**
   * Clear tornado track display.
   * @private
   */
  _clearTornadoTrack() {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;
    const layers = ['tornado-track-line', 'tornado-track-points', 'tornado-track-radius'];

    layers.forEach(id => {
      if (map.getLayer(id)) map.removeLayer(id);
    });

    if (map.getSource('tornado-track')) {
      map.removeSource('tornado-track');
    }
  },

  /**
   * Show exit control for track/drill-down mode.
   * @private
   */
  _showTrackExitControl() {
    // Remove any existing
    this._hideTrackExitControl();

    const exitBtn = document.createElement('button');
    exitBtn.id = 'track-exit-btn';
    exitBtn.textContent = 'Exit Track View';
    exitBtn.style.cssText = `
      position: absolute;
      top: 70px;
      right: 10px;
      z-index: 100;
      padding: 8px 16px;
      background: #2e7d32;
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 14px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.3);
    `;
    exitBtn.addEventListener('click', () => {
      this.exitTrackMode();
    });

    const mapContainer = MapAdapter?.map?.getContainer();
    if (mapContainer) {
      mapContainer.appendChild(exitBtn);
    }
  },

  /**
   * Hide track exit control.
   * @private
   */
  _hideTrackExitControl() {
    const existing = document.getElementById('track-exit-btn');
    if (existing) existing.remove();
  },

  /**
   * Exit track/drill-down mode.
   */
  exitTrackMode() {
    this._clearTornadoTrack();
    this._hideTrackExitControl();
    this._inTrackMode = false;
    MapAdapter?.hidePopup?.();
    MapAdapter.popupLocked = false;
    console.log('PointRadiusModel: Exited track mode');
  },

  /**
   * Exit runups view and restore original tsunami data.
   */
  exitRunupsMode() {
    if (!this._inRunupsMode || !this._originalTsunamiData) {
      console.log('PointRadiusModel: Not in runups mode, nothing to exit');
      return;
    }

    const sourceId = this._layerId('source', 'tsunami');
    const source = MapAdapter?.map?.getSource(sourceId);
    if (source) {
      source.setData(this._originalTsunamiData);
      console.log('PointRadiusModel: Restored original tsunami data');
    }

    // Clean up
    this._inRunupsMode = false;
    this._originalTsunamiData = null;
    this._hideRunupsExitControl();

    // Hide popup
    MapAdapter?.hidePopup?.();
    MapAdapter.popupLocked = false;
  },

  /**
   * Show an exit control for runups mode.
   * @private
   */
  _showRunupsExitControl() {
    // Remove any existing control
    this._hideRunupsExitControl();

    // Create a floating button on the map
    const exitBtn = document.createElement('button');
    exitBtn.id = 'runups-exit-btn';
    exitBtn.textContent = 'Exit Runups View';
    exitBtn.style.cssText = `
      position: absolute;
      top: 70px;
      right: 10px;
      z-index: 100;
      padding: 8px 16px;
      background: #004d40;
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 14px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.3);
    `;
    exitBtn.addEventListener('click', () => {
      this.exitRunupsMode();
    });

    // Add to map container
    const mapContainer = MapAdapter?.map?.getContainer();
    if (mapContainer) {
      mapContainer.appendChild(exitBtn);
    }
  },

  /**
   * Hide the runups exit control.
   * @private
   */
  _hideRunupsExitControl() {
    const existing = document.getElementById('runups-exit-btn');
    if (existing) {
      existing.remove();
    }
  },

  /**
   * Register callback for tsunami runups.
   * @param {Function} callback - Callback function
   */
  onTsunamiRunups(callback) {
    this.tsunamiRunupsCallback = callback;
  },

  /**
   * Register callback for fire animation events.
   * @param {Function} callback - Callback function
   */
  onFireAnimation(callback) {
    this.fireAnimationCallback = callback;
  },

  /**
   * Register callback for fire progression events (daily snapshots).
   * @param {Function} callback - Callback function receiving {snapshots, eventId, totalDays, startTime}
   */
  onFireProgression(callback) {
    this.fireProgressionCallback = callback;
  },

  /**
   * Notify about fire animation request.
   * @param {Object} perimeterData - GeoJSON perimeter from API
   * @param {string} eventId - Fire event ID
   * @param {number} durationDays - Fire duration in days
   * @param {string} timestamp - Fire ignition timestamp
   * @param {number} latitude - Ignition latitude
   * @param {number} longitude - Ignition longitude
   */
  _notifyFireAnimation(perimeterData, eventId, durationDays, timestamp, latitude, longitude) {
    console.log(`PointRadiusModel: Fire animation requested for ${eventId} (${durationDays} days)`);

    if (this.fireAnimationCallback) {
      this.fireAnimationCallback({
        perimeter: perimeterData,
        eventId: eventId,
        durationDays: durationDays,
        startTime: timestamp,
        latitude: latitude,
        longitude: longitude
      });
    } else {
      console.warn('PointRadiusModel: No fire animation callback registered');
    }
  },

  /**
   * Notify listeners that fire progression animation is requested.
   * Called when daily progression data is available.
   * @param {Object} progressionData - API response with daily snapshots
   * @param {string} eventId - Fire event ID
   * @param {string} timestamp - Fire ignition timestamp
   * @param {number} latitude - Ignition latitude
   * @param {number} longitude - Ignition longitude
   */
  _notifyFireProgression(progressionData, eventId, timestamp, latitude, longitude) {
    console.log(`PointRadiusModel: Fire progression requested for ${eventId} (${progressionData.total_days} daily snapshots)`);

    if (this.fireProgressionCallback) {
      this.fireProgressionCallback({
        snapshots: progressionData.snapshots,
        eventId: eventId,
        totalDays: progressionData.total_days,
        startTime: timestamp,
        latitude: latitude,
        longitude: longitude
      });
    } else if (this.fireAnimationCallback) {
      // Fall back to single-perimeter animation using last snapshot
      console.log('PointRadiusModel: No progression callback, falling back to single perimeter');
      const lastSnapshot = progressionData.snapshots[progressionData.snapshots.length - 1];
      this.fireAnimationCallback({
        perimeter: { type: 'Feature', geometry: lastSnapshot.geometry, properties: {} },
        eventId: eventId,
        durationDays: progressionData.total_days,
        startTime: timestamp,
        latitude: latitude,
        longitude: longitude
      });
    } else {
      console.warn('PointRadiusModel: No fire animation/progression callback registered');
    }
  },

  /**
   * Register callback for flood animation events.
   * @param {Function} callback - Callback function receiving {geometry, eventId, durationDays, startTime, endTime, latitude, longitude, eventName}
   */
  onFloodAnimation(callback) {
    this.floodAnimationCallback = callback;
  },

  /**
   * Notify about flood animation request.
   * @param {Object} geometryData - GeoJSON geometry from API
   * @param {string} eventId - Flood event ID
   * @param {number} durationDays - Flood duration in days
   * @param {string} startTime - Flood start timestamp
   * @param {string} endTime - Flood end timestamp
   * @param {number} latitude - Center latitude
   * @param {number} longitude - Center longitude
   * @param {string} eventName - Flood event name
   */
  _notifyFloodAnimation(geometryData, eventId, durationDays, startTime, endTime, latitude, longitude, eventName) {
    console.log(`PointRadiusModel: Flood animation requested for ${eventId} (${durationDays} days)`);

    if (this.floodAnimationCallback) {
      this.floodAnimationCallback({
        geometry: geometryData,
        eventId: eventId,
        durationDays: durationDays,
        startTime: startTime,
        endTime: endTime,
        latitude: latitude,
        longitude: longitude,
        eventName: eventName
      });
    } else {
      console.warn('PointRadiusModel: No flood animation callback registered');
    }
  },

  /**
   * Register callback for tornado sequence events.
   * @param {Function} callback - Callback function receiving {geojson, seedEventId, sequenceCount}
   */
  onTornadoSequence(callback) {
    this.tornadoSequenceCallback = callback;
  },

  /**
   * Notify about tornado sequence request.
   * @param {Object} sequenceData - GeoJSON FeatureCollection with linked tornadoes
   * @param {string} seedEventId - The tornado that was clicked
   */
  _notifyTornadoSequence(sequenceData, seedEventId) {
    const count = sequenceData.metadata?.total_count || sequenceData.features?.length || 0;
    console.log(`PointRadiusModel: Tornado sequence found with ${count} linked tornadoes`);

    if (this.tornadoSequenceCallback) {
      this.tornadoSequenceCallback({
        geojson: sequenceData,
        seedEventId: seedEventId,
        sequenceCount: count
      });
    } else {
      console.warn('PointRadiusModel: No tornado sequence callback registered');
      // Fall back to just displaying the sequence on the map
      this._displayTornadoSequence(sequenceData);
    }
  },

  /**
   * Register callback for point-only tornado animation (no track data).
   * @param {Function} callback - Callback function receiving {eventId, latitude, longitude, scale}
   */
  onTornadoPointAnimation(callback) {
    this.tornadoPointAnimationCallback = callback;
  },

  /**
   * Notify about point-only tornado animation request.
   * Used for tornadoes without track endpoints (e.g., Canadian tornadoes).
   * @param {string} eventId - Tornado event ID
   * @param {number} latitude - Tornado location latitude
   * @param {number} longitude - Tornado location longitude
   * @param {string} scale - Tornado scale (EF0-EF5)
   * @param {string} timestamp - ISO timestamp of the tornado event
   */
  _notifyTornadoPointAnimation(eventId, latitude, longitude, scale, timestamp) {
    console.log(`PointRadiusModel: Point-only tornado animation for ${eventId} at ${latitude}, ${longitude}`);

    if (this.tornadoPointAnimationCallback) {
      this.tornadoPointAnimationCallback({
        eventId: eventId,
        latitude: latitude,
        longitude: longitude,
        scale: scale,
        timestamp: timestamp
      });
    } else {
      console.warn('PointRadiusModel: No tornado point animation callback registered');
    }
  },

  // Tornado sequence animation state
  _tornadoSeqState: null,

  /**
   * Display a tornado sequence on the map with TimeSlider animation.
   * Shows linked tornado tracks appearing one by one as time advances.
   * @param {Object} sequenceData - GeoJSON FeatureCollection with linked tornadoes
   */
  _displayTornadoSequence(sequenceData) {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;
    const sourceId = 'tornado-sequence';
    const trackLayerId = 'tornado-sequence-tracks';
    const pointsLayerId = 'tornado-sequence-points';
    const connectLayerId = 'tornado-sequence-connect';

    // Clean up existing layers and animation state
    this._clearTornadoSequence();

    // Sort features by timestamp
    const sortedFeatures = sequenceData.features.sort((a, b) => {
      return new Date(a.properties.timestamp) - new Date(b.properties.timestamp);
    });

    // Extract timestamps for TimeSlider
    const timestamps = [];
    let minTime = Infinity, maxTime = -Infinity;
    for (const f of sortedFeatures) {
      const t = new Date(f.properties.timestamp).getTime();
      if (!isNaN(t)) {
        timestamps.push(t);
        if (t < minTime) minTime = t;
        if (t > maxTime) maxTime = t;
      }
    }
    timestamps.sort((a, b) => a - b);

    // If only one tornado or no valid timestamps, just show static display
    if (timestamps.length === 0 || minTime === maxTime) {
      this._displayTornadoSequenceStatic(sequenceData, sortedFeatures, map, sourceId, trackLayerId, pointsLayerId, connectLayerId);
      return;
    }

    // Build all possible features (will be filtered by time)
    const allFeatures = this._buildTornadoSequenceFeatures(sortedFeatures);

    // Add source with empty data (will be updated by time)
    map.addSource(sourceId, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] }
    });

    // Add connecting lines (dashed) - visible when tornado reaches that point
    map.addLayer({
      id: connectLayerId,
      type: 'line',
      source: sourceId,
      filter: ['==', ['get', 'feature_type'], 'connect'],
      paint: {
        'line-color': '#ffaa00',
        'line-width': 2,
        'line-dasharray': [4, 4],
        'line-opacity': 0.8
      }
    });

    // Add track lines
    map.addLayer({
      id: trackLayerId,
      type: 'line',
      source: sourceId,
      filter: ['==', ['get', 'feature_type'], 'track'],
      paint: {
        'line-color': ['case',
          ['==', ['get', 'is_seed'], true], '#ff4500',
          '#32cd32'
        ],
        'line-width': 5,
        'line-opacity': 0.9
      }
    });

    // Add endpoint markers
    map.addLayer({
      id: pointsLayerId,
      type: 'circle',
      source: sourceId,
      filter: ['in', ['get', 'feature_type'], ['literal', ['start', 'end']]],
      paint: {
        'circle-radius': 8,
        'circle-color': ['case',
          ['==', ['get', 'feature_type'], 'start'], '#00ff00',
          '#ff0000'
        ],
        'circle-stroke-color': '#222',
        'circle-stroke-width': 2
      }
    });

    // Fit bounds to full sequence
    const bounds = new maplibregl.LngLatBounds();
    extendBoundsWithCoordinateList(bounds, this._sequenceBoundsCoords(sortedFeatures));
    map.fitBounds(bounds, { padding: 80, duration: 1000, maxZoom: 10 });

    // Hide popup
    MapAdapter?.hidePopup?.();
    MapAdapter.popupLocked = false;

    // Setup TimeSlider scale
    const scaleId = `tornado-seq-${Date.now()}`;
    const firstDate = new Date(minTime).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

    // Store animation state
    this._tornadoSeqState = {
      sourceId,
      trackLayerId,
      pointsLayerId,
      connectLayerId,
      scaleId,
      allFeatures,
      sortedFeatures,
      minTime,
      maxTime,
      timeChangeHandler: null
    };

    if (TimeSlider) {
      const added = TimeSlider.addScale({
        id: scaleId,
        label: `Tornado Sequence ${firstDate} (${sortedFeatures.length} paths)`,
        granularity: '1h',  // Tornado sequences typically span hours
        useTimestamps: true,
        currentTime: minTime,
        timeRange: {
          min: minTime,
          max: maxTime,
          available: timestamps
        },
        mapRenderer: 'tornado-sequence'
      });

      if (added) {
        TimeSlider.setActiveScale(scaleId);

        // Enter event animation mode with auto-calculated ~3 second playback
        if (TimeSlider.enterEventAnimation) {
          TimeSlider.enterEventAnimation(minTime, maxTime);
        }

        // Listen for time changes to filter visible features
        this._tornadoSeqState.timeChangeHandler = (time) => {
          this._updateTornadoSequenceForTime(time);
        };
        TimeSlider.addChangeListener(this._tornadoSeqState.timeChangeHandler);
      }
    }

    // Render initial state (first tornado)
    this._updateTornadoSequenceForTime(minTime);

    // Show exit button
    this._showSequenceExitControl();

    console.log(`PointRadiusModel: Displayed tornado sequence with ${sortedFeatures.length} tornadoes, TimeSlider enabled`);
  },

  /**
   * Build all features for tornado sequence (tracks, endpoints, connections).
   * @private
   */
  _buildTornadoSequenceFeatures(sortedFeatures) {
    const features = [];

    sortedFeatures.forEach((f, idx) => {
      const props = f.properties;
      const timestamp = new Date(props.timestamp).getTime();

      // Track line
      if (props.track && props.track.coordinates) {
        features.push({
          type: 'Feature',
          geometry: props.track,
          properties: { ...props, feature_type: 'track', seq_idx: idx, _timestamp: timestamp }
        });
      }

      // Start endpoint
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [props.longitude, props.latitude] },
        properties: { ...props, feature_type: 'start', seq_idx: idx, _timestamp: timestamp }
      });

      // End endpoint
      if (props.end_latitude && props.end_longitude) {
        features.push({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [props.end_longitude, props.end_latitude] },
          properties: { ...props, feature_type: 'end', seq_idx: idx, _timestamp: timestamp }
        });

        // Connection to next tornado (visible when current tornado ends)
        if (idx < sortedFeatures.length - 1) {
          const next = sortedFeatures[idx + 1].properties;
          features.push({
            type: 'Feature',
            geometry: {
              type: 'LineString',
              coordinates: [
                [props.end_longitude, props.end_latitude],
                [next.longitude, next.latitude]
              ]
            },
            properties: { feature_type: 'connect', seq_idx: idx, _timestamp: timestamp }
          });
        }
      }
    });

    return features;
  },

  /**
   * Update tornado sequence display for current time.
   * Shows only tornadoes that have occurred by this time.
   * @private
   */
  _updateTornadoSequenceForTime(currentTime) {
    if (!this._tornadoSeqState || !MapAdapter?.map) return;

    const { sourceId, allFeatures } = this._tornadoSeqState;
    const source = MapAdapter.map.getSource(sourceId);
    if (!source) return;

    // Filter features to those at or before current time
    const visibleFeatures = allFeatures.filter(f => {
      const featureTime = f.properties._timestamp;
      return featureTime <= currentTime;
    });

    // Update source data
    source.setData({
      type: 'FeatureCollection',
      features: visibleFeatures
    });
  },

  /**
   * Display static tornado sequence (no animation, single tornado or no timestamps).
   * @private
   */
  _displayTornadoSequenceStatic(sequenceData, sortedFeatures, map, sourceId, trackLayerId, pointsLayerId, connectLayerId) {
    const features = this._buildTornadoSequenceFeatures(sortedFeatures);

    // Add source with all features
    map.addSource(sourceId, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features }
    });

    // Add layers
    map.addLayer({
      id: connectLayerId,
      type: 'line',
      source: sourceId,
      filter: ['==', ['get', 'feature_type'], 'connect'],
      paint: {
        'line-color': '#ffaa00',
        'line-width': 2,
        'line-dasharray': [4, 4],
        'line-opacity': 0.8
      }
    });

    map.addLayer({
      id: trackLayerId,
      type: 'line',
      source: sourceId,
      filter: ['==', ['get', 'feature_type'], 'track'],
      paint: {
        'line-color': ['case',
          ['==', ['get', 'is_seed'], true], '#ff4500',
          '#32cd32'
        ],
        'line-width': 5,
        'line-opacity': 0.9
      }
    });

    map.addLayer({
      id: pointsLayerId,
      type: 'circle',
      source: sourceId,
      filter: ['in', ['get', 'feature_type'], ['literal', ['start', 'end']]],
      paint: {
        'circle-radius': 8,
        'circle-color': ['case',
          ['==', ['get', 'feature_type'], 'start'], '#00ff00',
          '#ff0000'
        ],
        'circle-stroke-color': '#222',
        'circle-stroke-width': 2
      }
    });

    // Fit bounds
    const bounds = new maplibregl.LngLatBounds();
    extendBoundsWithCoordinateList(bounds, this._sequenceBoundsCoords(sortedFeatures));
    map.fitBounds(bounds, { padding: 80, duration: 1000, maxZoom: 10 });

    // Hide popup
    MapAdapter?.hidePopup?.();
    MapAdapter.popupLocked = false;

    // Store minimal state for cleanup
    this._tornadoSeqState = {
      sourceId,
      trackLayerId,
      pointsLayerId,
      connectLayerId,
      scaleId: null,
      allFeatures: features,
      sortedFeatures,
      minTime: null,
      maxTime: null,
      timeChangeHandler: null
    };

    // Show exit button
    this._showSequenceExitControl();

    console.log(`PointRadiusModel: Displayed static tornado sequence with ${sortedFeatures.length} tornadoes`);
  },

  /**
   * Show exit control for tornado sequence view.
   * Positioned at top center to match other animators (EventAnimator, SequenceAnimator).
   * @private
   */
  _showSequenceExitControl() {
    this._hideSequenceExitControl();

    // Create container at top center (matching EventAnimator/SequenceAnimator style)
    const container = document.createElement('div');
    container.id = 'tornado-sequence-exit-container';
    container.style.cssText = `
      position: fixed;
      top: 80px;
      left: 50%;
      transform: translateX(-50%);
      display: flex;
      gap: 12px;
      z-index: 1000;
    `;

    const exitBtn = document.createElement('button');
    exitBtn.id = 'sequence-exit-btn';
    exitBtn.textContent = 'Exit Sequence View';
    exitBtn.style.cssText = `
      padding: 10px 20px;
      background: #6b7280;
      color: white;
      border: none;
      border-radius: 6px;
      cursor: pointer;
      font-size: 14px;
      font-weight: 500;
      box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    `;
    exitBtn.addEventListener('click', () => {
      this._clearTornadoSequence();
      this._hideSequenceExitControl();
    });

    container.appendChild(exitBtn);
    document.body.appendChild(container);
  },

  /**
   * Hide sequence exit control.
   * @private
   */
  _hideSequenceExitControl() {
    const container = document.getElementById('tornado-sequence-exit-container');
    if (container) container.remove();
    // Also check for old button ID for backwards compatibility
    const existingBtn = document.getElementById('sequence-exit-btn');
    if (existingBtn) existingBtn.remove();
  },

  /**
   * Clear tornado sequence display.
   * @private
   */
  _clearTornadoSequence() {
    if (!MapAdapter?.map) return;

    const map = MapAdapter.map;
    const layers = ['tornado-sequence-tracks', 'tornado-sequence-points', 'tornado-sequence-connect'];

    layers.forEach(id => {
      if (map.getLayer(id)) map.removeLayer(id);
    });

    if (map.getSource('tornado-sequence')) {
      map.removeSource('tornado-sequence');
    }

    console.log('PointRadiusModel: Cleared tornado sequence');
  },

  /**
   * Get events in a sequence.
   * @param {string} sequenceId - Sequence ID
   * @param {string} eventType - Event type (defaults to 'earthquake' since sequences are earthquake-specific)
   * @returns {Array} Array of features in the sequence
   */
  getSequenceEvents(sequenceId, eventType = 'earthquake') {
    if (!MapAdapter?.map) return [];

    const sourceId = this._layerId('source', eventType);
    const source = MapAdapter.map.getSource(sourceId);
    if (!source || !source._data) return [];

    return source._data.features.filter(f =>
      f.properties.sequence_id === sequenceId
    );
  },

  /**
   * Collect [lon, lat] pairs from sequence features (start point plus
   * optional end point) for shared bounds union.
   * @private
   */
  _sequenceBoundsCoords(features) {
    const coords = [];
    features.forEach(f => {
      coords.push([f.properties.longitude, f.properties.latitude]);
      if (f.properties.end_longitude && f.properties.end_latitude) {
        coords.push([f.properties.end_longitude, f.properties.end_latitude]);
      }
    });
    return coords;
  },

  /**
   * Fit map to event bounds.
   * @param {Object} geojson - Event GeoJSON
   */
  fitBounds(geojson) {
    if (!MapAdapter?.map || !geojson || !geojson.features || geojson.features.length === 0) {
      return;
    }

    const pointCoords = [];

    for (const feature of geojson.features) {
      if (feature.geometry && feature.geometry.type === 'Point') {
        const coords = feature.geometry.coordinates;
        if (Array.isArray(coords) && coords.length >= 2) {
          const lon = Number(coords[0]);
          const lat = Number(coords[1]);
          if (Number.isFinite(lon) && Number.isFinite(lat)) {
            pointCoords.push([lon, lat]);
          }
        }
      }
    }

    if (pointCoords.length === 1) {
      MapAdapter.flyTo(pointCoords[0], 8);
      return;
    }

    const bounds = new maplibregl.LngLatBounds();
    extendBoundsWithCoordinateList(bounds, pointCoords);

    if (!bounds.isEmpty()) {
      MapAdapter.map.fitBounds(bounds, {
        padding: 50,
        duration: 1000,
        maxZoom: 10
      });
    }
  },

  /**
   * Build HTML popup content for event.
   * @param {Object} props - Feature properties
   * @param {string} eventType - Event type
   * @returns {string} HTML string
   */
  buildPopupHtml(props, eventType) {
    const lines = [];

    if (eventType === 'earthquake') {
      const mag = props.magnitude?.toFixed(1) || 'N/A';
      lines.push(`<strong>M${mag} Earthquake</strong>`);
      if (props.place) lines.push(props.place);
      if (props.depth_km != null) lines.push(`Depth: ${props.depth_km.toFixed(1)} km`);
      if (props.timestamp) {
        const date = new Date(props.timestamp);
        lines.push(date.toLocaleString());
      } else if (props.time) {
        const date = new Date(props.time);
        lines.push(date.toLocaleString());
      }
      // Show impact radii
      if (props.damage_radius_km > 0) {
        lines.push(`Damage radius: ${props.damage_radius_km.toFixed(0)} km`);
      }
      if (props.felt_radius_km > 0) {
        lines.push(`Felt radius: ${props.felt_radius_km.toFixed(0)} km`);
      }
      // Aftershock sequence info
      if (props.is_mainshock && props.aftershock_count > 0) {
        lines.push(`<span style="color:#4fc3f7">Aftershocks: ${props.aftershock_count.toLocaleString()}</span>`);
        lines.push(`<a href="#" class="view-sequence-link" data-sequence="${props.sequence_id}" data-eventid="${props.event_id}" style="color:#81c784;text-decoration:underline;cursor:pointer">View sequence</a>`);
      } else if (props.mainshock_id) {
        lines.push(`<span style="color:#ffb74d">Aftershock of larger event</span>`);
        if (props.sequence_id) {
          lines.push(`<a href="#" class="view-sequence-link" data-sequence="${props.sequence_id}" data-eventid="${props.event_id}" style="color:#81c784;text-decoration:underline;cursor:pointer">View sequence</a>`);
        }
      }
      // Cross-link to volcanoes: look for eruptions that may have triggered this earthquake
      // Only for modern earthquakes where volcano data overlaps (1900+)
      if (props.year >= 1900 || (props.timestamp && new Date(props.timestamp).getFullYear() >= 1900)) {
        const lat = props.latitude || props.lat;
        const lon = props.longitude || props.lng || props.lon;
        if (lat != null && lon != null) {
          const ts = props.timestamp || props.time || '';
          const yr = props.year || (props.timestamp ? new Date(props.timestamp).getFullYear() : null);
          lines.push(`<a href="#" class="find-volcanoes-link" data-lat="${lat}" data-lon="${lon}" data-timestamp="${ts}" data-year="${yr}" style="color:#feb24c;text-decoration:underline;cursor:pointer">Find related volcanoes</a>`);
        }
      }
    } else if (eventType === 'volcano') {
      lines.push(`<strong>${props.volcano_name || 'Volcanic Eruption'}</strong>`);
      // Show VEI or Unknown (unknown = green marker)
      lines.push(`VEI: ${props.VEI != null ? props.VEI : 'Unknown'}`);
      if (props.activity_type) lines.push(`Type: ${props.activity_type}`);
      // Show activity area if available (e.g., "East rift zone")
      if (props.activity_area) lines.push(`Area: ${props.activity_area}`);
      // Display year/date range with duration for long eruptions
      if (props.year != null) {
        const startYear = props.year < 0 ? `${Math.abs(props.year)} BCE` : props.year;
        // Check if this is a multi-year eruption (has end_year different from start)
        if (props.end_year != null && !isNaN(props.end_year) && props.end_year !== props.year) {
          // Multi-year eruption - show range
          const endYear = props.is_ongoing ? 'ongoing' : props.end_year;
          lines.push(`Years: ${startYear} - ${endYear}`);
          // Show duration in appropriate units
          if (props.duration_days != null && !isNaN(props.duration_days) && props.duration_days > 0) {
            const years = props.duration_days / 365.25;
            if (years >= 1) {
              lines.push(`Duration: ${years.toFixed(1)} years`);
            } else {
              lines.push(`Duration: ${Math.round(props.duration_days)} days`);
            }
          }
        } else {
          // Single year or short eruption
          lines.push(`Year: ${startYear}`);
          // Show specific date if available
          if (props.timestamp) {
            const date = new Date(props.timestamp);
            if (!isNaN(date.getTime())) {
              lines.push(date.toLocaleDateString());
            }
          }
        }
      }
      // Show ongoing status prominently
      if (props.is_ongoing === true || props.is_ongoing === 'true') {
        lines.push(`<span style="color:#ff9800">ONGOING</span>`);
      }
      // Show impact radii
      if (props.damage_radius_km > 0) {
        lines.push(`Damage radius: ${Math.round(props.damage_radius_km)} km`);
      }
      if (props.felt_radius_km > 0) {
        lines.push(`Felt radius: ${Math.round(props.felt_radius_km)} km`);
      }
      // Cross-link to earthquakes: only for modern eruptions (1900+) where earthquake data exists
      if (props.year != null && props.year >= 1900) {
        // Store coordinates as data attributes for the fetch
        const lat = props.latitude || props.lat;
        const lon = props.longitude || props.lng || props.lon;
        if (lat != null && lon != null) {
          const ts = props.timestamp || '';
          lines.push(`<a href="#" class="find-earthquakes-link" data-lat="${lat}" data-lon="${lon}" data-timestamp="${ts}" data-year="${props.year}" data-volcano="${props.volcano_name || 'volcano'}" style="color:#4fc3f7;text-decoration:underline;cursor:pointer">Find related earthquakes</a>`);
        }
      }
    } else if (eventType === 'tsunami') {
      // Tsunami - different display for source vs runup
      // Check both is_source (API) and _isSource (animation enriched)
      if (props.is_source || props._isSource) {
        // Source epicenter
        lines.push('<strong>Tsunami Source</strong>');
        if (props.cause) lines.push(`Cause: ${props.cause}`);
        if (props.eq_magnitude) lines.push(`Magnitude: M${props.eq_magnitude.toFixed(1)}`);
        if (props.max_water_height_m != null) {
          lines.push(`Max wave height: ${props.max_water_height_m.toFixed(1)} m`);
        }
        if (props.timestamp) {
          const date = new Date(props.timestamp);
          lines.push(date.toLocaleString());
        } else if (props.year) {
          const yearStr = props.year < 0 ? `${Math.abs(props.year)} BCE` : props.year;
          lines.push(`Year: ${yearStr}`);
        }
        // Casualties
        if (props.deaths != null && props.deaths > 0) {
          lines.push(`<span style="color:#ef5350">Deaths: ${props.deaths.toLocaleString()}</span>`);
        }
        if (props.injuries != null && props.injuries > 0) {
          lines.push(`Injuries: ${props.injuries.toLocaleString()}`);
        }
        // Runup count
        if (props.runup_count != null && props.runup_count > 0) {
          lines.push(`<span style="color:#4dd0e1">Runups recorded: ${props.runup_count}</span>`);
          if (props.event_id) {
            lines.push(`<a href="#" class="view-runups-link" data-event="${props.event_id}" style="color:#81c784;text-decoration:underline;cursor:pointer">View runups</a>`);
          }
        }
      } else {
        // Coastal runup observation
        lines.push('<strong>Coastal Runup</strong>');
        if (props.location_name) lines.push(props.location_name);
        if (props.country) lines.push(props.country);
        if (props.water_height_m != null) {
          lines.push(`Wave height: ${props.water_height_m.toFixed(1)} m`);
        }
        if (props.dist_from_source_km != null) {
          lines.push(`Distance from source: ${Math.round(props.dist_from_source_km)} km`);
        }
        // Travel time
        if (props.travel_time_hours != null) {
          const hours = props.travel_time_hours;
          if (hours < 1) {
            lines.push(`Travel time: ${Math.round(hours * 60)} min`);
          } else {
            lines.push(`Travel time: ${hours.toFixed(1)} hours`);
          }
        }
        // Runup casualties
        if (props.deaths != null && props.deaths > 0) {
          lines.push(`<span style="color:#ef5350">Deaths: ${props.deaths.toLocaleString()}</span>`);
        }
      }
    } else if (eventType === 'wildfire') {
      // Wildfire popup
      lines.push('<strong style="color:#ff6600">Wildfire</strong>');

      // Size info
      if (props.area_km2 != null) {
        const areaKm2 = props.area_km2;
        const acres = props.burned_acres || (areaKm2 * 247.105);
        lines.push(`Area: ${areaKm2.toLocaleString(undefined, {maximumFractionDigits: 0})} km2 (${Math.round(acres).toLocaleString()} acres)`);
      }

      // Duration
      if (props.duration_days != null && props.duration_days > 0) {
        lines.push(`Duration: ${props.duration_days} days`);
      }

      // Date
      if (props.timestamp) {
        const date = new Date(props.timestamp);
        lines.push(`Ignition: ${date.toLocaleDateString()}`);
      } else if (props.year) {
        lines.push(`Year: ${props.year}`);
      }

      // Land cover / vegetation type
      if (props.land_cover) {
        lines.push(`Vegetation: ${props.land_cover}`);
      }

      // Location
      if (props.latitude != null && props.longitude != null) {
        lines.push(`Location: ${props.latitude.toFixed(3)}, ${props.longitude.toFixed(3)}`);
      }

      // View fire animation link
      if (props.event_id && props.duration_days > 1) {
        lines.push(`<a href="#" class="view-fire-link" data-event="${props.event_id}" data-duration="${props.duration_days}" data-timestamp="${props.timestamp}" data-year="${props.year || ''}" data-lat="${props.latitude || ''}" data-lon="${props.longitude || ''}" style="color:#ff9800;text-decoration:underline;cursor:pointer">View fire progression</a>`);
      }
    } else if (eventType === 'flood') {
      // Flood popup
      lines.push('<strong style="color:#0066cc">Flood Event</strong>');

      // Event name if available
      if (props.event_name) {
        lines.push(`<span style="color:#3399ff">${props.event_name}</span>`);
      }

      // Location info
      if (props.country) {
        lines.push(`Location: ${props.country}`);
      }

      // Duration
      if (props.duration_days != null && props.duration_days > 0) {
        lines.push(`Duration: ${props.duration_days} days`);
      }

      // Date range
      if (props.timestamp && props.end_timestamp) {
        const start = new Date(props.timestamp);
        const end = new Date(props.end_timestamp);
        lines.push(`${start.toLocaleDateString()} - ${end.toLocaleDateString()}`);
      } else if (props.timestamp) {
        const date = new Date(props.timestamp);
        lines.push(`Started: ${date.toLocaleDateString()}`);
      } else if (props.year) {
        lines.push(`Year: ${props.year}`);
      }

      // Casualties
      if (props.dead_count != null && props.dead_count > 0) {
        lines.push(`<span style="color:#ef5350">Deaths: ${props.dead_count.toLocaleString()}</span>`);
      }
      if (props.displaced_count != null && props.displaced_count > 0) {
        lines.push(`Displaced: ${props.displaced_count.toLocaleString()}`);
      }

      // Data source
      if (props.source) {
        lines.push(`<span style="color:#888">Source: ${props.source}</span>`);
      }

      // View flood animation link
      if (props.event_id && props.duration_days > 1) {
        lines.push(`<a href="#" class="view-flood-link" data-event="${props.event_id}" data-duration="${props.duration_days}" data-start="${props.timestamp || ''}" data-end="${props.end_timestamp || ''}" data-name="${props.event_name || ''}" data-lat="${props.latitude || ''}" data-lon="${props.longitude || ''}" style="color:#0066cc;text-decoration:underline;cursor:pointer">View flood extent</a>`);
      }
    } else if (eventType === 'tornado') {
      // Tornado popup
      const scale = props.tornado_scale || 'Unknown';
      // Color the header by scale
      const scaleColors = {
        'EF0': '#98fb98', 'F0': '#98fb98',
        'EF1': '#32cd32', 'F1': '#32cd32',
        'EF2': '#ffd700', 'F2': '#ffd700',
        'EF3': '#ff8c00', 'F3': '#ff8c00',
        'EF4': '#ff4500', 'F4': '#ff4500',
        'EF5': '#8b0000', 'F5': '#8b0000'
      };
      const scaleColor = scaleColors[scale] || '#ffffff';
      lines.push(`<strong style="color:${scaleColor}">${scale} Tornado</strong>`);

      // Scale description
      const scaleDesc = {
        'EF0': 'Light damage', 'F0': 'Light damage',
        'EF1': 'Moderate damage', 'F1': 'Moderate damage',
        'EF2': 'Significant damage', 'F2': 'Significant damage',
        'EF3': 'Severe damage', 'F3': 'Severe damage',
        'EF4': 'Devastating damage', 'F4': 'Devastating damage',
        'EF5': 'Incredible damage', 'F5': 'Incredible damage'
      };
      if (scaleDesc[scale]) {
        lines.push(`<span style="color:#aaa">${scaleDesc[scale]}</span>`);
      }

      // Track dimensions
      if (props.path_length_miles != null && props.path_length_miles > 0) {
        lines.push(`Path length: ${props.path_length_miles.toFixed(1)} miles`);
      }
      if (props.path_width_yards != null && props.path_width_yards > 0) {
        lines.push(`Path width: ${props.path_width_yards} yards`);
      }

      // Date/time
      if (props.timestamp) {
        const date = new Date(props.timestamp);
        lines.push(date.toLocaleString());
      } else if (props.year) {
        lines.push(`Year: ${props.year}`);
      }

      // Casualties
      if (props.deaths_direct != null && props.deaths_direct > 0) {
        lines.push(`<span style="color:#ef5350">Deaths: ${props.deaths_direct}</span>`);
      }
      if (props.injuries_direct != null && props.injuries_direct > 0) {
        lines.push(`Injuries: ${props.injuries_direct}`);
      }

      // Property damage
      if (props.damage_property != null && props.damage_property > 0) {
        const damage = props.damage_property >= 1e9
          ? `$${(props.damage_property / 1e9).toFixed(1)}B`
          : props.damage_property >= 1e6
          ? `$${(props.damage_property / 1e6).toFixed(1)}M`
          : `$${props.damage_property.toLocaleString()}`;
        lines.push(`Property damage: ${damage}`);
      }

      // View track link - only if end coordinates available (shows static track)
      const hasTrack = props.end_latitude != null || props.end_lat != null;
      if (props.event_id && hasTrack) {
        lines.push(`<a href="#" class="view-tornado-track-link" data-event="${props.event_id}" style="color:#32cd32;text-decoration:underline;cursor:pointer">View tornado track</a>`);
      }

      // Animate tornado - always available
      // With track: animates along path. Without track: zooms and shows fading circle
      if (props.event_id) {
        const seqCount = props.sequence_count || 1;
        let linkText;
        if (seqCount > 1) {
          linkText = `Animate tornado sequence (${seqCount} paths)`;
        } else if (hasTrack) {
          linkText = 'Animate tornado path';
        } else {
          linkText = 'Animate tornado';
        }
        // Store hasTrack and timestamp in data attributes for animation handler
        lines.push(`<a href="#" class="view-tornado-sequence-link" data-event="${props.event_id}" data-hastrack="${hasTrack}" data-lat="${props.latitude || ''}" data-lon="${props.longitude || ''}" data-scale="${props.tornado_scale || ''}" data-timestamp="${props.timestamp || ''}" style="color:#ffa500;text-decoration:underline;cursor:pointer">${linkText}</a>`);
      }
    } else {
      // Generic popup
      lines.push(`<strong>${eventType} Event</strong>`);
      if (props.event_id) lines.push(`ID: ${props.event_id}`);
    }

    return lines.join('<br>');
  },

  /**
   * Build simplified hover preview HTML.
   * Shows just essential info - click for full popup.
   * @param {Object} props - Feature properties
   * @param {string} eventType - Event type
   * @returns {string} HTML string
   */
  buildHoverPreview(props, eventType) {
    let title = '';
    let subtitle = '';
    let stat = '';

    switch (eventType) {
      case 'earthquake':
        const mag = props.magnitude?.toFixed(1) || 'N/A';
        title = `M${mag} Earthquake`;
        subtitle = props.place || '';
        if (props.depth_km != null) {
          stat = `Depth: ${props.depth_km.toFixed(1)} km`;
        }
        break;

      case 'volcano':
        title = props.volcano_name || 'Volcanic Eruption';
        stat = props.VEI != null ? `VEI ${props.VEI}` : '';
        subtitle = props.year ? (props.year < 0 ? `${Math.abs(props.year)} BCE` : `${props.year}`) : '';
        break;

      case 'tsunami':
        if (props.is_source || props._isSource) {
          title = 'Tsunami Source';
          stat = props.eq_magnitude ? `M${props.eq_magnitude.toFixed(1)}` : '';
        } else {
          title = 'Coastal Runup';
          stat = props.water_height_m != null ? `${props.water_height_m.toFixed(1)}m` : '';
        }
        subtitle = props.cause || '';
        break;

      case 'wildfire':
        title = 'Wildfire';
        if (props.area_km2 != null) {
          stat = `${props.area_km2.toLocaleString(undefined, {maximumFractionDigits: 0})} km2`;
        }
        if (props.timestamp) {
          subtitle = new Date(props.timestamp).toLocaleDateString();
        }
        break;

      case 'flood':
        title = props.event_name || 'Flood Event';
        subtitle = props.country || '';
        if (props.duration_days != null) {
          stat = `${props.duration_days} days`;
        }
        break;

      case 'tornado':
        const scale = props.tornado_scale || 'Unknown';
        title = `${scale} Tornado`;
        if (props.timestamp) {
          subtitle = new Date(props.timestamp).toLocaleDateString();
        }
        if (props.path_length_miles != null) {
          stat = `${props.path_length_miles.toFixed(1)} mi path`;
        }
        break;

      case 'landslide':
        title = props.event_name || 'Landslide';
        if (props.timestamp) {
          subtitle = new Date(props.timestamp).toLocaleDateString();
        }
        if (props.deaths != null && props.deaths > 0) {
          stat = `${props.deaths} deaths`;
        }
        break;

      default:
        title = `${eventType} Event`;
        if (props.event_id) subtitle = props.event_id;
    }

    let html = `<strong>${title}</strong>`;
    if (subtitle) html += `<br><span style="color:#666">${subtitle}</span>`;
    if (stat) html += `<br>${stat}`;
    html += `<br><span style="color:#0f4c75;font-size:11px">Click for details</span>`;

    return html;
  },

  /**
   * Check if this model is currently active.
   * @returns {boolean}
   */
  isActive() {
    return this.activeType !== null;
  },

  /**
   * Get the currently active event type.
   * @returns {string|null}
   */
  getActiveType() {
    return this.activeType;
  },

  /**
   * Setup global event listeners for DisasterPopup buttons.
   * Bridges the new popup system to existing animation handlers.
   * @private
   */
  _setupPopupEventListeners() {
    // Only setup once
    if (this._popupListenersSetup) return;
    this._popupListenersSetup = true;

    const model = this; // Capture reference for event handlers

    // NOTE: disaster-sequence-request is now handled by ModelRegistry central dispatcher
    // which routes to this model's handleSequence() method

    document.addEventListener('disaster-sequence-data-request', async (e) => {
      const { eventId, eventType, props } = e.detail || {};
      if (eventType !== 'earthquake' || !eventId) {
        return;
      }

      const cacheKey = `eqseq_${eventType}_${eventId}`;

      try {
        const data = await fetchMsgpack(`/api/earthquakes/aftershocks/${encodeURIComponent(eventId)}`);
        const features = Array.isArray(data?.features) ? data.features : [];
        if (!features.length) {
          if (window.DisasterPopup && window.DisasterPopup.state === 'SEQUENCE_CONFIRM') {
            window.DisasterPopup.cachedData[cacheKey] = {
              anchor_event: { ...props, sequence_context_key: cacheKey },
              mainshock: { ...props, sequence_context_key: cacheKey },
              total_count: 0,
              visible_count: 0,
              events: []
            };
            window.DisasterPopup.state = 'SEQUENCE';
            const html = window.DisasterPopup.buildEarthquakeSequencePopup(
              window.DisasterPopup.cachedData[cacheKey].anchor_event,
              eventType,
              window.DisasterPopup.cachedData[cacheKey]
            );
            window.DisasterPopup.updatePopupContent(html);
          }
          return;
        }

        let mainshock = features.find((feature) => feature?.properties?.is_mainshock);
        if (!mainshock) {
          mainshock = features.reduce((best, candidate) => {
            const bestMag = Number(best?.properties?.magnitude) || 0;
            const candidateMag = Number(candidate?.properties?.magnitude) || 0;
            return candidateMag > bestMag ? candidate : best;
          }, features[0]);
        }

        const normalizedEvents = features
          .map((feature) => ({ ...(feature?.properties || {}) }))
          .filter((candidate) => String(candidate?.event_id || '').trim())
          .sort((a, b) => {
            if (a.is_mainshock && !b.is_mainshock) return -1;
            if (!a.is_mainshock && b.is_mainshock) return 1;
            const aTime = a?.timestamp ? new Date(a.timestamp).getTime() : Number.POSITIVE_INFINITY;
            const bTime = b?.timestamp ? new Date(b.timestamp).getTime() : Number.POSITIVE_INFINITY;
            return aTime - bTime;
          });

        const visibleEvents = normalizedEvents.slice(0, 50);

        if (window.DisasterPopup) {
          window.DisasterPopup.cachedData[cacheKey] = {
            anchor_event: { ...props, sequence_context_key: cacheKey },
            mainshock: { ...(mainshock?.properties || {}), sequence_context_key: cacheKey },
            total_count: normalizedEvents.length,
            visible_count: visibleEvents.length,
            events: visibleEvents.map((event) => ({
              ...event,
              sequence_context_key: cacheKey
            }))
          };
          if (window.DisasterPopup.state === 'SEQUENCE_CONFIRM') {
            window.DisasterPopup.state = 'SEQUENCE';
            const html = window.DisasterPopup.buildEarthquakeSequencePopup(
              window.DisasterPopup.cachedData[cacheKey].anchor_event,
              eventType,
              window.DisasterPopup.cachedData[cacheKey]
            );
            window.DisasterPopup.updatePopupContent(html);
          }
        }
      } catch (err) {
        console.error('Error fetching earthquake sequence data:', err);
        if (window.DisasterPopup && window.DisasterPopup.state === 'SEQUENCE_CONFIRM') {
          window.DisasterPopup.cachedData[cacheKey] = {
            anchor_event: { ...props, sequence_context_key: cacheKey },
            mainshock: { ...props, sequence_context_key: cacheKey },
            total_count: 0,
            visible_count: 0,
            events: []
          };
          window.DisasterPopup.state = 'SEQUENCE';
          const html = window.DisasterPopup.buildEarthquakeSequencePopup(
            window.DisasterPopup.cachedData[cacheKey].anchor_event,
            eventType,
            window.DisasterPopup.cachedData[cacheKey]
          );
          window.DisasterPopup.updatePopupContent(html);
        }
      }
    });

    // Handle Related button clicks - uses links.parquet via API
    document.addEventListener('disaster-related-request', async (e) => {
      const { eventId, eventType, props } = e.detail;

      // Use unified loc_id directly from props (stored in parquet files)
      const unifiedLocId = props.loc_id;
      if (!unifiedLocId) {
        console.warn('Related disasters request skipped: missing loc_id', { eventId, eventType, props });
        if (window.DisasterPopup) {
          window.DisasterPopup.cachedData[`rel_${eventType}_${eventId}`] = {
            related: [],
            count: 0,
            message: 'Related-disaster links are unavailable for this event because its loc_id is missing.'
          };
          if (window.DisasterPopup.state === 'RELATED_CONFIRM' || window.DisasterPopup.state === 'RELATED') {
            const html = window.DisasterPopup.state === 'RELATED'
              ? window.DisasterPopup.buildRelatedPopup(
                window.DisasterPopup.currentEvent,
                window.DisasterPopup.currentType,
                window.DisasterPopup.cachedData[`rel_${eventType}_${eventId}`]
              )
              : window.DisasterPopup.buildRelatedConfirmPopup(
                window.DisasterPopup.currentEvent,
                window.DisasterPopup.currentType,
                window.DisasterPopup.cachedData[`rel_${eventType}_${eventId}`]
              );
            window.DisasterPopup.updatePopupContent(html);
          }
        }
        return;
      }

      try {
        const url = `/api/events/related/${encodeURIComponent(unifiedLocId)}?cross_type_only=true`;
        const data = await fetchMsgpack(url);

        if (data.count > 0) {
          // Update the popup with related data
          if (window.DisasterPopup) {
            window.DisasterPopup.cachedData[`rel_${eventType}_${eventId}`] = {
              related: data.related,
              count: data.count || data.related?.length || 0,
              message: data.message || null
            };
            if (window.DisasterPopup.state === 'RELATED_CONFIRM' || window.DisasterPopup.state === 'RELATED') {
              const html = window.DisasterPopup.state === 'RELATED'
                ? window.DisasterPopup.buildRelatedPopup(
                  window.DisasterPopup.currentEvent,
                  window.DisasterPopup.currentType,
                  window.DisasterPopup.cachedData[`rel_${eventType}_${eventId}`]
                )
                : window.DisasterPopup.buildRelatedConfirmPopup(
                window.DisasterPopup.currentEvent,
                window.DisasterPopup.currentType,
                window.DisasterPopup.cachedData[`rel_${eventType}_${eventId}`]
                );
              window.DisasterPopup.updatePopupContent(html);
            }
          }
          console.log(`Found ${data.count} related events:`, data.by_type);
        } else {
          console.log('No related events found in links table', { eventId, eventType, unifiedLocId, message: data.message });
          if (window.DisasterPopup) {
            window.DisasterPopup.cachedData[`rel_${eventType}_${eventId}`] = {
              related: [],
              count: 0,
              message: data.message || null
            };
            if (window.DisasterPopup.state === 'RELATED_CONFIRM' || window.DisasterPopup.state === 'RELATED') {
              const html = window.DisasterPopup.state === 'RELATED'
                ? window.DisasterPopup.buildRelatedPopup(
                  window.DisasterPopup.currentEvent,
                  window.DisasterPopup.currentType,
                  window.DisasterPopup.cachedData[`rel_${eventType}_${eventId}`]
                )
                : window.DisasterPopup.buildRelatedConfirmPopup(
                window.DisasterPopup.currentEvent,
                window.DisasterPopup.currentType,
                window.DisasterPopup.cachedData[`rel_${eventType}_${eventId}`]
                );
              window.DisasterPopup.updatePopupContent(html);
            }
          }

          // Fallback to proximity search for earthquakes/volcanoes
          if (eventType === 'earthquake' && props.latitude && props.longitude) {
            const lat = props.latitude;
            const lon = props.longitude;
            const timestamp = props.timestamp;
            const year = props.year || (timestamp ? new Date(timestamp).getFullYear() : null);

            let fallbackUrl = `/api/events/nearby-volcanoes?lat=${lat}&lon=${lon}&radius_km=150`;
            if (timestamp) {
              fallbackUrl += `&timestamp=${encodeURIComponent(timestamp)}&days_before=60`;
            } else if (year) {
              fallbackUrl += `&year=${year}`;
            }

            const fallbackData = await fetchMsgpack(fallbackUrl);
            if (fallbackData.count > 0) {
              model._notifyNearbyVolcanoes(fallbackData.features, lat, lon);
            }
          } else if (eventType === 'volcano' && props.latitude && props.longitude) {
            const lat = props.latitude;
            const lon = props.longitude;
            const timestamp = props.timestamp;
            const year = props.year;
            const volcanoName = props.volcano_name || 'volcano';

            let fallbackUrl = `/api/events/nearby-earthquakes?lat=${lat}&lon=${lon}&radius_km=150&min_magnitude=3.0`;
            if (timestamp) {
              fallbackUrl += `&timestamp=${encodeURIComponent(timestamp)}&days_before=30&days_after=60`;
            } else if (year) {
              fallbackUrl += `&year=${year}`;
            }

            const fallbackData = await fetchMsgpack(fallbackUrl);
            if (fallbackData.count > 0) {
              const volcanoSeqId = `volcano-${volcanoName}-${year}`;
              model._notifyVolcanoEarthquakes(fallbackData.features, volcanoSeqId, volcanoName, lat, lon);
            }
          }
        }
      } catch (err) {
        console.error('Error fetching related events:', err);
      }
    });

    document.addEventListener('disaster-history-request', async (e) => {
      const { eventId, eventType, props } = e.detail || {};
      if (eventType !== 'volcano' || !props?.route_focus_anchor || !props?.latitude || !props?.longitude) {
        return;
      }

      const cacheKey = `hist_${eventType}_${eventId || props.volcano_name || 'focus'}`;

      try {
        const historyRadiusKm = 20;
        const url = `/api/events/nearby-volcanoes?lat=${props.latitude}&lon=${props.longitude}&radius_km=${historyRadiusKm}`;
        const data = await fetchMsgpack(url);
        const features = Array.isArray(data?.features) ? data.features : [];
        const targetName = String(props.volcano_name || '').trim();
        const normalizeName = (value) => String(value || '')
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, ' ')
          .trim();
        const normalizedTarget = normalizeName(targetName);
        const matchedFeatures = normalizedTarget
          ? features.filter((feature) => normalizeName(feature?.properties?.volcano_name) === normalizedTarget)
          : features;
        const events = (matchedFeatures.length ? matchedFeatures : features)
          .map((feature) => ({ ...(feature?.properties || {}) }))
          .filter((candidate) => String(candidate?.event_id || '').trim())
          .sort((a, b) => {
            const aYear = Number(a?.year);
            const bYear = Number(b?.year);
            if (Number.isFinite(aYear) && Number.isFinite(bYear) && aYear !== bYear) {
              return bYear - aYear;
            }
            const aTime = a?.timestamp ? new Date(a.timestamp).getTime() : Number.NEGATIVE_INFINITY;
            const bTime = b?.timestamp ? new Date(b.timestamp).getTime() : Number.NEGATIVE_INFINITY;
            return bTime - aTime;
          });

        if (window.DisasterPopup) {
          window.DisasterPopup.cachedData[cacheKey] = {
            anchor_event: { ...props, history_context_key: cacheKey },
            volcano_name: targetName || props.volcano_name || 'Volcano',
            radius_km: historyRadiusKm,
            events
          };
          if (window.DisasterPopup.state === 'HISTORY_CONFIRM') {
            const html = window.DisasterPopup.buildHistoryPopup(
              window.DisasterPopup.currentEvent,
              window.DisasterPopup.currentType,
              window.DisasterPopup.cachedData[cacheKey]
            );
            window.DisasterPopup.updatePopupContent(html);
          }
        }
      } catch (err) {
        console.error('Error fetching volcano history:', err);
        if (window.DisasterPopup) {
          window.DisasterPopup.cachedData[cacheKey] = { events: [] };
          if (window.DisasterPopup.state === 'HISTORY_CONFIRM') {
            const html = window.DisasterPopup.buildHistoryPopup(
              window.DisasterPopup.currentEvent,
              window.DisasterPopup.currentType,
              window.DisasterPopup.cachedData[cacheKey]
            );
            window.DisasterPopup.updatePopupContent(html);
          }
        }
      }
    });

    document.addEventListener('disaster-related-click', async (e) => {
      const { eventId, eventType, locId } = e.detail || {};
      const resolvedLocId = String(locId || '').trim();

      if (!resolvedLocId) {
        console.warn('Related disaster click skipped: missing loc_id', { eventId, eventType });
        return;
      }

      try {
        const data = await fetchMsgpack(`/api/events/by-loc/${encodeURIComponent(resolvedLocId)}`);
        const feature = Array.isArray(data?.features) ? data.features[0] : null;
        const props = feature?.properties || null;
        const targetType = props?.event_type || data?.event_type || eventType;
        const targetEventId = props?.event_id || eventId;

        if (!props || !targetType || !targetEventId) {
          console.warn('Related disaster click could not resolve a target event', { resolvedLocId, eventType, eventId, data });
          return;
        }

        if (window.DisasterPopup) {
          window.DisasterPopup.hide();
        }

        // Open the linked event's own detail popup, even when its overlay is
        // not loaded: fly to it and show the popup directly. handleSequence
        // alone only fires animation notifications that need the target
        // hazard's overlay to be active, which made linked events look inert.
        const coords = feature.geometry?.coordinates;
        if (Array.isArray(coords) && coords.length >= 2) {
          MapAdapter?.flyTo?.(coords, 7);
          if (window.DisasterPopup?.show) {
            window.DisasterPopup.show(coords, props, targetType);
          }
        }

        await this.handleSequence(targetEventId, targetType, props);
      } catch (err) {
        console.error('Error opening related disaster:', err);
      }
    });

    document.addEventListener('disaster-related-chain-request', async (e) => {
      const { eventType, props } = e.detail || {};
      const resolvedLocId = String(props?.loc_id || '').trim();
      if (!resolvedLocId) {
        console.warn('Related chain request skipped: missing loc_id', { eventType, props });
        return;
      }

      try {
        const data = await fetchMsgpack(`/api/events/chain/${encodeURIComponent(resolvedLocId)}?depth=2&cross_type_only=true`);
        if (Array.isArray(data?.features) && data.features.length > 1) {
          this._notifyRelatedChain(data);
        } else {
          console.warn('Related chain returned no linked events', { resolvedLocId, data });
        }
      } catch (err) {
        console.error('Error fetching related disaster chain:', err);
      }
    });

    console.log('DisasterPopup event listeners initialized');
  }
};
