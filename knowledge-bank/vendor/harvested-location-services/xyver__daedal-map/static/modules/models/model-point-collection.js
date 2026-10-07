/**
 * Point collection model for durable locations (POIs, sensors, facilities).
 *
 * Unlike PointRadiusModel, this is deliberately non-eventful: it clusters
 * dense point sets, renders a reusable pin/icon, and opens a compact record
 * popup.  A dataset can supply an SVG icon through the render options.
 */

let MapAdapter = null;

export function setDependencies(deps) {
  MapAdapter = deps.MapAdapter;
}

const DEFAULT_PIN_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 32">
  <path d="M12 1.5C6.3 1.5 1.8 6 1.8 11.7c0 7.6 10.2 18.8 10.2 18.8s10.2-11.2 10.2-18.8C22.2 6 17.7 1.5 12 1.5Z" fill="#33c3ff" stroke="#06233a" stroke-width="2"/>
  <circle cx="12" cy="11.5" r="4" fill="#f8fbff"/>
</svg>`;

const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[char]));

export const PointCollectionModel = {
  entries: new Map(),

  _ids(id) {
    const safe = String(id || 'points').replace(/[^a-z0-9_-]+/gi, '-');
    return {
      source: `point-collection-${safe}-source`,
      cluster: `point-collection-${safe}-cluster`,
      clusterCount: `point-collection-${safe}-cluster-count`,
      pin: `point-collection-${safe}-pin`,
      icon: `point-collection-${safe}-icon`,
    };
  },

  async _ensureIcon(map, imageId, svg) {
    if (map.hasImage(imageId)) return;
    const image = new Image(32, 42);
    await new Promise((resolve, reject) => {
      image.onload = () => {
        try {
          if (!map.hasImage(imageId)) map.addImage(imageId, image, { pixelRatio: 2 });
          resolve();
        } catch (error) { reject(error); }
      };
      image.onerror = reject;
      image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg || DEFAULT_PIN_SVG)}`;
    });
  },

  _popupHtml(props, options) {
    const popup = options.popup || {};
    const facilityType = String(props?.facility_type || '').replace(/[_-]+/g, ' ').trim();
    const facilityTitle = facilityType ? facilityType.replace(/\b\w/g, (char) => char.toUpperCase()) : '';
    // Some public registries have a valid type but no stable facility name.
    // A semantic fallback is more useful than an anonymous "Location" card.
    const title = props?.[popup.titleProp || popup.title_prop || 'name'] || props?.name || facilityTitle || props?.city || 'Location';
    const configuredFields = Array.isArray(popup.fields) ? popup.fields : [
      { prop: 'facility_type', label: 'Type' },
      { prop: 'source', label: 'Source' },
      { prop: 'country_iso2', label: 'Country' },
    ];
    const rows = configuredFields.map((field) => {
      const value = props?.[field.prop];
      if (value == null || value === '') return '';
      return `<div><span style="color:#8ca0b7">${escapeHtml(field.label || field.prop)}:</span> ${escapeHtml(value)}${field.unit ? ` ${escapeHtml(field.unit)}` : ''}</div>`;
    }).join('');
    return `<div class="point-collection-popup" style="font-size:12px;line-height:1.45;max-width:240px">
      <div style="font-weight:700">${escapeHtml(title)}</div>${rows}
    </div>`;
  },

  async render(id, geojson, options = {}) {
    const map = MapAdapter?.map;
    if (!map || !geojson?.features?.length) return false;
    const ids = this._ids(id);
    const iconSvg = options.icon?.svg || DEFAULT_PIN_SVG;
    await this._ensureIcon(map, ids.icon, iconSvg);

    const source = map.getSource(ids.source);
    if (source) {
      source.setData(geojson);
      this.entries.set(id, { ids, options });
      return true;
    }

    map.addSource(ids.source, {
      type: 'geojson', data: geojson, cluster: true,
      clusterMaxZoom: options.clusterMaxZoom ?? 10,
      clusterRadius: options.clusterRadius ?? 35,
    });
    map.addLayer({
      id: ids.cluster, type: 'circle', source: ids.source, filter: ['has', 'point_count'],
      paint: { 'circle-color': options.clusterColor || '#087fb8', 'circle-radius': ['step', ['get', 'point_count'], 11.25, 25, 15, 100, 19.5], 'circle-opacity': 0.92, 'circle-stroke-color': '#dff6ff', 'circle-stroke-width': 1.4 }
    });
    map.addLayer({
      id: ids.clusterCount, type: 'symbol', source: ids.source, filter: ['has', 'point_count'],
      layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-font': ['Open Sans Bold'], 'text-size': 12 },
      paint: { 'text-color': '#ffffff' }
    });
    map.addLayer({
      id: ids.pin, type: 'symbol', source: ids.source, filter: ['!', ['has', 'point_count']],
      layout: { 'icon-image': ids.icon, 'icon-size': options.icon?.size ?? ['interpolate', ['linear'], ['zoom'], 2, 0.44, 7, 0.62, 12, 0.82], 'icon-anchor': 'bottom', 'icon-allow-overlap': true, 'icon-ignore-placement': true }
    });

    map.on('click', ids.cluster, (event) => {
      const cluster = event.features?.[0];
      const clusterId = cluster?.properties?.cluster_id;
      if (clusterId == null) return;
      map.getSource(ids.source).getClusterExpansionZoom(clusterId, (error, zoom) => {
        if (!error) map.easeTo({ center: cluster.geometry.coordinates, zoom });
      });
    });
    map.on('click', ids.pin, (event) => {
      const feature = event.features?.[0];
      if (!feature) return;
      MapAdapter?.registerFeaturePopupClick?.();
      MapAdapter?.showPopup?.([event.lngLat.lng, event.lngLat.lat], this._popupHtml(feature.properties || {}, options));
      if (MapAdapter) MapAdapter.popupLocked = true;
    });
    for (const layerId of [ids.cluster, ids.pin]) {
      map.on('mouseenter', layerId, () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', layerId, () => { map.getCanvas().style.cursor = ''; });
    }
    this.entries.set(id, { ids, options });
    return true;
  },

  clear(id) {
    const map = MapAdapter?.map;
    const entry = this.entries.get(id);
    if (!map || !entry) return;
    for (const layerId of [entry.ids.pin, entry.ids.clusterCount, entry.ids.cluster]) {
      if (map.getLayer(layerId)) map.removeLayer(layerId);
    }
    if (map.getSource(entry.ids.source)) map.removeSource(entry.ids.source);
    this.entries.delete(id);
  },

  clearAllExcept(id = null) {
    for (const entryId of [...this.entries.keys()]) {
      if (entryId !== id) this.clear(entryId);
    }
  },
};
