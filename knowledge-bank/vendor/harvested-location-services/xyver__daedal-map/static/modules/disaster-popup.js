/**
 * Unified Disaster Popup System
 *
 * Provides consistent popup UI across all disaster types with:
 * - Quick stats cards (Power, Time, Impact)
 * - Three action buttons (Details, Sequence, Related)
 * - State machine for popup transitions
 *
 * See docs/DISASTER_DISPLAY.md for full specification.
 */

import { CONFIG } from './config.js';
import { fetchMsgpack } from './utils/fetch.js';

const DisasterPopup = {
  // Current popup state
  state: 'CLOSED', // CLOSED, BASIC, DETAIL, SEQUENCE_CONFIRM, RELATED_CONFIRM, RELATED
  currentEvent: null,
  currentType: null,
  cachedData: {}, // Cache for sequence/related data
  basicCountCache: {},

  // Event type icons
  icons: {
    earthquake: 'E',
    volcano: 'V',
    tsunami: 'T',
    hurricane: 'H',
    tornado: 'N',
    wildfire: 'W',
    flood: 'F',
    drought: 'D',
    landslide: 'L',
    generic: '*'
  },

  // Event type colors
  colors: {
    earthquake: '#ff6b6b',
    volcano: '#feb24c',
    tsunami: '#4dd0e1',
    hurricane: '#9c27b0',
    tornado: '#32cd32',
    wildfire: '#ff6600',
    flood: '#0066cc',
    drought: '#d2691e',  // Saddle brown for drought
    landslide: '#8b4513',  // Sienna brown for landslides
    generic: '#888888'
  },

  getVolcanoHistoryColor(vei) {
    const palette = CONFIG?.volcanoColors || {};
    const numericVei = Number(vei);
    if (!Number.isFinite(numericVei)) {
      return '#44ff44';
    }
    const bucket = Math.max(0, Math.min(7, Math.round(numericVei)));
    return palette[bucket] || palette.default || '#ffcc00';
  },

  getEarthquakeSequenceColor(magnitude) {
    const numericMag = Number(magnitude);
    if (!Number.isFinite(numericMag)) {
      return '#90caf9';
    }
    if (numericMag >= 8) return '#b71c1c';
    if (numericMag >= 7) return '#d32f2f';
    if (numericMag >= 6) return '#f57c00';
    if (numericMag >= 5) return '#fbc02d';
    return '#81c784';
  },

  /**
   * Format power stat based on disaster type
   */
  formatPower(props, eventType) {
    switch (eventType) {
      case 'earthquake':
        const mag = props.magnitude?.toFixed(1) || 'N/A';
        return { label: 'Power', value: `M ${mag}`, detail: 'Magnitude' };

      case 'tsunami':
        const height = props.max_water_height_m;
        if (height != null) {
          return { label: 'Power', value: `${height.toFixed(1)}m`, detail: 'Max wave height' };
        }
        const eqMag = props.eq_magnitude;
        if (eqMag != null) {
          return { label: 'Power', value: `M ${eqMag.toFixed(1)}`, detail: 'Triggering quake' };
        }
        return { label: 'Power', value: 'N/A', detail: '' };

      case 'volcano':
        const vei = props.VEI;
        if (vei != null) {
          return { label: 'Power', value: `VEI ${vei}`, detail: 'Eruption index' };
        }
        if (props.route_focus_anchor) {
          return { label: 'State', value: 'Dormant', detail: 'No active eruption' };
        }
        return { label: 'Power', value: 'Quiet', detail: 'No VEI recorded' };

      case 'hurricane':
      case 'tropical_storm':
        const cat = props.category || props.max_category;
        const wind = props.wind_kt || props.max_wind_kt;
        if (cat != null) {
          return { label: 'Power', value: `Cat ${cat}`, detail: wind ? `${wind} kt` : '' };
        }
        if (wind != null) {
          return { label: 'Power', value: `${wind} kt`, detail: 'Max wind' };
        }
        return { label: 'Power', value: 'N/A', detail: '' };

      case 'tornado':
        const scale = props.tornado_scale || 'Unknown';
        return { label: 'Power', value: scale, detail: this.getTornadoDescription(scale) };

      case 'wildfire':
        const area = props.area_km2;
        if (area != null) {
          if (area >= 1000) {
            return { label: 'Size', value: `${(area/1000).toFixed(1)}K km2`, detail: 'Burned area' };
          }
          return { label: 'Size', value: `${Math.round(area)} km2`, detail: 'Burned area' };
        }
        return { label: 'Size', value: 'N/A', detail: '' };

      case 'flood':
        const severity = props.severity || props.flood_severity;
        if (severity) {
          return { label: 'Severity', value: severity, detail: '' };
        }
        const floodArea = props.area_km2;
        if (floodArea != null) {
          return { label: 'Area', value: `${Math.round(floodArea)} km2`, detail: 'Affected area' };
        }
        return { label: 'Severity', value: 'N/A', detail: '' };

      case 'drought':
        const droughtSeverity = props.severity;
        const severityName = props.severity_name;
        if (droughtSeverity) {
          return { label: 'Severity', value: droughtSeverity, detail: severityName || '' };
        }
        return { label: 'Severity', value: 'N/A', detail: '' };

      case 'landslide':
        const deaths = props.deaths;
        if (deaths != null && deaths > 0) {
          return { label: 'Deaths', value: deaths.toString(), detail: 'Fatalities' };
        }
        return { label: 'Impact', value: 'Recorded', detail: '' };

      default:
        return { label: 'Power', value: 'N/A', detail: '' };
    }
  },

  /**
   * Calculate duration in days from two timestamps
   */
  calculateDurationDays(start, end) {
    const startDate = new Date(start);
    const endDate = new Date(end);
    if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) return null;
    return Math.round((endDate - startDate) / (1000 * 60 * 60 * 24));
  },

  /**
   * Format duration days into human readable string
   */
  formatDurationDays(days) {
    if (days == null || days <= 0) return null;
    if (days >= 365) {
      const years = (days / 365).toFixed(1);
      return { label: 'Duration', value: `${years} yr`, detail: `${days} days` };
    }
    if (days >= 30) {
      const months = Math.round(days / 30);
      return { label: 'Duration', value: `${months} mo`, detail: `${days} days` };
    }
    return { label: 'Duration', value: `${days} days`, detail: '' };
  },

  /**
   * Format time/duration stat based on disaster type
   */
  formatTime(props, eventType) {
    // Check for explicit duration first
    const durationDays = props.duration_days;
    const durationMinutes = props.duration_minutes;

    if (durationDays != null && durationDays > 0) {
      const formatted = this.formatDurationDays(durationDays);
      if (formatted) return formatted;
    }

    if (durationMinutes != null && durationMinutes > 0) {
      if (durationMinutes >= 60) {
        const hours = (durationMinutes / 60).toFixed(1);
        return { label: 'Duration', value: `${hours} hr`, detail: '' };
      }
      return { label: 'Duration', value: `${durationMinutes} min`, detail: '' };
    }

    // Calculate duration from start/end timestamps if available
    if (props.start_date && props.end_date) {
      const days = this.calculateDurationDays(props.start_date, props.end_date);
      const formatted = this.formatDurationDays(days);
      if (formatted) return formatted;
    }
    if (props.timestamp && props.end_timestamp) {
      const days = this.calculateDurationDays(props.timestamp, props.end_timestamp);
      const formatted = this.formatDurationDays(days);
      if (formatted) return formatted;
    }

    // Type-specific time formatting
    switch (eventType) {
      case 'earthquake':
        // Earthquakes are instantaneous, show shaking estimate
        const mag = props.magnitude || 0;
        const shakeSec = Math.max(10, Math.round(Math.pow(10, (mag - 5) * 0.5) * 10));
        return { label: 'Shaking', value: `~${shakeSec}s`, detail: 'Estimated' };

      case 'tsunami':
        // Show travel time or runup count
        if (props.travel_time_hours != null) {
          const hrs = props.travel_time_hours;
          if (hrs < 1) {
            return { label: 'Travel', value: `${Math.round(hrs * 60)} min`, detail: 'To coast' };
          }
          return { label: 'Travel', value: `${hrs.toFixed(1)} hr`, detail: 'To coast' };
        }
        return { label: 'Time', value: 'N/A', detail: '' };

      case 'hurricane':
      case 'tropical_storm':
        // Already handled above, fallback
        return { label: 'Duration', value: 'N/A', detail: '' };

      case 'tornado':
        // Estimate duration from path length (avg tornado speed ~30 mph)
        const pathMiles = props.path_length_miles || props.tornado_length_mi;
        if (pathMiles != null && pathMiles > 0) {
          const estMinutes = Math.max(1, Math.round(pathMiles * 2)); // ~30 mph avg forward speed
          if (estMinutes >= 60) {
            return { label: 'Time', value: `~${(estMinutes/60).toFixed(1)} hr`, detail: 'Estimated' };
          }
          return { label: 'Time', value: `~${estMinutes} min`, detail: 'Estimated' };
        }
        return { label: 'Time', value: 'Brief', detail: 'Seconds to minutes' };

      case 'volcano':
        if (props.is_ongoing) {
          return { label: 'Status', value: 'Ongoing', detail: 'Still active' };
        }
        // Try to calculate from timestamp + end_year
        if (props.timestamp && props.end_year) {
          const startYear = new Date(props.timestamp).getUTCFullYear();
          const yearDiff = props.end_year - startYear;
          if (yearDiff > 0) {
            return { label: 'Duration', value: `${yearDiff} yr`, detail: '' };
          }
        }
        return { label: 'Duration', value: 'N/A', detail: '' };

      case 'wildfire':
        // Wildfires should have duration_days from data
        return { label: 'Duration', value: 'N/A', detail: '' };

      case 'flood':
        // Floods should have duration_days or timestamps
        return { label: 'Duration', value: 'N/A', detail: '' };

      case 'landslide':
        // Landslides are sudden events
        return { label: 'Time', value: 'Sudden', detail: 'Minutes to hours' };

      default:
        return { label: 'Time', value: 'N/A', detail: '' };
    }
  },

  /**
   * Format large numbers with K/M/B suffix
   */
  formatLargeNumber(num) {
    if (num >= 1e9) return `${(num / 1e9).toFixed(1)}B`;
    if (num >= 1e6) return `${(num / 1e6).toFixed(1)}M`;
    if (num >= 1e3) return `${(num / 1e3).toFixed(1)}K`;
    return num.toLocaleString();
  },

  /**
   * Format impact stat based on disaster type
   */
  formatImpact(props, eventType) {
    // Check for deaths first - always a primary impact metric
    const deaths = props.deaths || props.deaths_direct;
    if (deaths != null && deaths > 0) {
      return { label: 'Deaths', value: this.formatLargeNumber(deaths), detail: '' };
    }

    switch (eventType) {
      case 'earthquake':
        const feltKm = props.felt_radius_km;
        if (feltKm != null && feltKm > 0) {
          if (feltKm >= 1000) {
            return { label: 'Felt', value: `${(feltKm/1000).toFixed(1)}K km`, detail: 'Radius' };
          }
          return { label: 'Felt', value: `${Math.round(feltKm)} km`, detail: 'Radius' };
        }
        // Fallback to depth
        if (props.depth_km != null) {
          return { label: 'Depth', value: `${props.depth_km.toFixed(1)} km`, detail: '' };
        }
        return { label: 'Impact', value: 'N/A', detail: '' };

      case 'tsunami':
        const runups = props.runup_count;
        if (runups != null && runups > 0) {
          return { label: 'Runups', value: runups.toString(), detail: 'Coastal impacts' };
        }
        // Show max distance if available
        if (props.max_runup_dist_km != null && props.max_runup_dist_km > 0) {
          return { label: 'Reach', value: `${Math.round(props.max_runup_dist_km)} km`, detail: 'Max distance' };
        }
        return { label: 'Impact', value: 'N/A', detail: '' };

      case 'volcano':
        const damageKm = props.damage_radius_km;
        if (damageKm != null && damageKm > 0) {
          return { label: 'Damage', value: `${Math.round(damageKm)} km`, detail: 'Radius' };
        }
        // Show felt radius as fallback
        if (props.felt_radius_km != null && props.felt_radius_km > 0) {
          return { label: 'Felt', value: `${Math.round(props.felt_radius_km)} km`, detail: 'Radius' };
        }
        return { label: 'Impact', value: 'N/A', detail: '' };

      case 'hurricane':
      case 'tropical_storm':
        // Show if it made landfall
        if (props.made_landfall === true) {
          const maxWind = props.max_wind_kt || props.wind_kt;
          return { label: 'Landfall', value: 'Yes', detail: maxWind ? `${maxWind} kt max` : '' };
        }
        if (props.made_landfall === false) {
          return { label: 'Landfall', value: 'No', detail: 'Remained at sea' };
        }
        const maxWind = props.max_wind_kt || props.wind_kt;
        if (maxWind != null) {
          return { label: 'Wind', value: `${maxWind} kt`, detail: 'Maximum' };
        }
        return { label: 'Impact', value: 'N/A', detail: '' };

      case 'tornado':
        const pathLen = props.path_length_miles || props.tornado_length_mi;
        const pathWidth = props.path_width_yards || props.tornado_width_yd;
        if (pathLen != null && pathLen > 0) {
          const widthStr = pathWidth ? `${pathWidth} yd wide` : '';
          return { label: 'Path', value: `${pathLen.toFixed(1)} mi`, detail: widthStr };
        }
        return { label: 'Impact', value: 'N/A', detail: '' };

      case 'wildfire':
        // Show area burned in appropriate units
        const areaKm2 = props.area_km2;
        if (areaKm2 != null && areaKm2 > 0) {
          if (areaKm2 >= 1000) {
            return { label: 'Burned', value: `${(areaKm2/1000).toFixed(1)}K km2`, detail: '' };
          }
          return { label: 'Burned', value: `${Math.round(areaKm2)} km2`, detail: '' };
        }
        const acres = props.burned_acres;
        if (acres != null && acres > 0) {
          if (acres >= 1000) {
            return { label: 'Burned', value: `${(acres/1000).toFixed(1)}K ac`, detail: '' };
          }
          return { label: 'Burned', value: `${Math.round(acres)} ac`, detail: '' };
        }
        return { label: 'Impact', value: 'N/A', detail: '' };

      case 'flood':
        // Show displaced population
        const displaced = props.displaced;
        if (displaced != null && displaced > 0) {
          return { label: 'Displaced', value: this.formatLargeNumber(displaced), detail: 'People' };
        }
        // Show area affected
        const floodArea = props.area_km2;
        if (floodArea != null && floodArea > 0) {
          if (floodArea >= 1000) {
            return { label: 'Area', value: `${(floodArea/1000).toFixed(1)}K km2`, detail: 'Affected' };
          }
          return { label: 'Area', value: `${Math.round(floodArea)} km2`, detail: 'Affected' };
        }
        return { label: 'Impact', value: 'N/A', detail: '' };

      case 'landslide':
        // Show affected or houses destroyed
        const affected = props.affected;
        if (affected != null && affected > 0) {
          return { label: 'Affected', value: this.formatLargeNumber(affected), detail: 'People' };
        }
        const houses = props.houses_destroyed;
        if (houses != null && houses > 0) {
          return { label: 'Homes', value: this.formatLargeNumber(houses), detail: 'Destroyed' };
        }
        return { label: 'Impact', value: 'Recorded', detail: '' };

      default:
        return { label: 'Impact', value: 'N/A', detail: '' };
    }
  },

  /**
   * Get tornado scale description
   */
  getTornadoDescription(scale) {
    const descriptions = {
      'EF0': 'Light', 'F0': 'Light',
      'EF1': 'Moderate', 'F1': 'Moderate',
      'EF2': 'Significant', 'F2': 'Significant',
      'EF3': 'Severe', 'F3': 'Severe',
      'EF4': 'Devastating', 'F4': 'Devastating',
      'EF5': 'Incredible', 'F5': 'Incredible'
    };
    return descriptions[scale] || '';
  },

  /**
   * Get event title
   */
  getTitle(props, eventType) {
    switch (eventType) {
      case 'earthquake':
        const mag = props.magnitude?.toFixed(1) || 'N/A';
        return `M${mag} Earthquake`;

      case 'tsunami':
        if (props.is_source || props._isSource) {
          return 'Tsunami Source';
        }
        return 'Coastal Runup';

      case 'volcano':
        return props.volcano_name || 'Volcanic Eruption';

      case 'hurricane':
      case 'tropical_storm':
        const name = props.name || props.storm_name;
        if (name) {
          return name;
        }
        return 'Tropical Storm';

      case 'tornado':
        const scale = props.tornado_scale || 'Unknown';
        return `${scale} Tornado`;

      case 'wildfire':
        return props.fire_name || 'Wildfire';

      case 'flood':
        return props.event_name || 'Flood Event';

      case 'landslide':
        return props.event_name || 'Landslide';

      default:
        return `${eventType} Event`;
    }
  },

  /**
   * Format a date nicely (e.g., "Jan 15, 2020")
   */
  formatDate(timestamp) {
    if (!timestamp) return null;
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) return null;
    // Check for very old dates (before year 100)
    const year = date.getUTCFullYear();
    if (year < 100 && year > -100) {
      return year < 0 ? `${Math.abs(year)} BCE` : `${year} CE`;
    }
    return date.toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC'
    });
  },

  /**
   * Format a date range (e.g., "Jul 28 - Aug 5, 2020")
   */
  formatDateRange(startTimestamp, endTimestamp) {
    const start = new Date(startTimestamp);
    const end = new Date(endTimestamp);
    if (isNaN(start.getTime()) || isNaN(end.getTime())) return null;

    const startYear = start.getUTCFullYear();
    const endYear = end.getUTCFullYear();

    if (startYear === endYear) {
      // Same year: "Jul 28 - Aug 5, 2020"
      const startStr = start.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
      const endStr = end.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
      return `${startStr} - ${endStr}`;
    } else {
      // Different years: "Dec 28, 2019 - Jan 5, 2020"
      const startStr = start.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
      const endStr = end.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
      return `${startStr} - ${endStr}`;
    }
  },

  /**
   * Get event subtitle (location, date)
   */
  getSubtitle(props, eventType) {
    const parts = [];

    // Location
    if (props.place) {
      parts.push(props.place);
    } else if (props.location) {
      parts.push(props.location);
    } else if (props.location_name) {
      parts.push(props.location_name);
    } else if (props.country) {
      parts.push(props.country);
    }

    // Date - prefer date ranges for events with duration
    if (props.start_date && props.end_date) {
      // Hurricane/storm date range
      const range = this.formatDateRange(props.start_date, props.end_date);
      if (range) parts.push(range);
    } else if (props.timestamp && props.end_timestamp) {
      // Volcano/flood date range
      const range = this.formatDateRange(props.timestamp, props.end_timestamp);
      if (range) parts.push(range);
    } else if (props.timestamp) {
      // Single timestamp
      const dateStr = this.formatDate(props.timestamp);
      if (dateStr) parts.push(dateStr);
    } else if (props.year) {
      // Fallback to year only
      const yr = props.year < 0 ? `${Math.abs(props.year)} BCE` : props.year;
      parts.push(yr.toString());
    }

    return parts.join(' - ');
  },

  /**
   * Check if event has sequence data
   */
  hasSequence(props, eventType) {
    // Middle button always enabled for basic animation (impact radius, path, etc.)
    // Even without linked events, we show a solo animation for the event itself
    switch (eventType) {
      case 'earthquake':
        // Always show - at minimum displays impact radius animation
        return true;

      case 'tsunami':
        // Always show - at minimum displays wave impact animation
        return true;

      case 'hurricane':
      case 'tropical_storm':
        // Always show - has track data
        return true;

      case 'tornado':
        // Always show - at minimum displays path or point animation
        return true;

      case 'volcano':
        // Always show - at minimum displays impact radius animation
        return true;

      case 'wildfire':
        // Always show - at minimum displays area circle, enhanced with progression data
        return true;

      case 'flood':
        // Always show - at minimum displays area circle, enhanced with geometry data
        return true;

      case 'landslide':
        // No sequence data for landslides
        return false;

      default:
        return false;
    }
  },

  /**
   * Get sequence button text
   */
  getSequenceText(props, eventType) {
    const numericCounts = [
      props.aftershock_count,
      props.runup_count,
      props.sequence_count,
      props.history_count,
      props.impact_count
    ].map((value) => Number(value)).filter((value) => Number.isFinite(value) && value > 0);
    const genericCount = numericCounts.length ? numericCounts[0] : null;

    switch (eventType) {
      case 'earthquake':
        if (props.aftershock_count > 0) {
          return `Aftershocks (${props.aftershock_count})`;
        }
        return 'Chain';

      case 'tsunami':
        if (props.runup_count > 0) {
          return `Runups (${props.runup_count})`;
        }
        return 'Runups';

      case 'hurricane':
      case 'tropical_storm':
        return 'Track';

      case 'tornado':
        if (props.sequence_count > 1) {
          return `Sequence (${props.sequence_count})`;
        }
        return 'Path';

      case 'volcano':
        if (genericCount) {
          return `Impact (${genericCount})`;
        }
        return 'Impact';

      case 'wildfire':
        return 'Progression';

      case 'flood':
        return 'Extent';

      case 'landslide':
        if (genericCount) {
          return `Impact (${genericCount})`;
        }
        return 'Impact';

      default:
        return 'Sequence';
    }
  },

  getRelatedCount(props, eventType) {
    if (Array.isArray(props.related_events) && props.related_events.length > 0) {
      return props.related_events.length;
    }

    if (props.eq_event_id) return 1;
    if (props.volcano_id) return 1;
    if (props.hurricane_id) return 1;
    if (props.tsunami_event_id) return 1;

    if (Array.isArray(props.earthquake_event_ids) && props.earthquake_event_ids.length > 0) {
      return props.earthquake_event_ids.length;
    }

    if (typeof props.earthquake_event_ids === 'string' && props.earthquake_event_ids.trim()) {
      return props.earthquake_event_ids
        .split(/[,\s;|]+/)
        .map((value) => String(value || '').trim())
        .filter(Boolean)
        .length;
    }

    if (eventType === 'tsunami' && String(props.cause || '').trim()) {
      return 1;
    }

    return null;
  },

  getRelatedText(props, eventType) {
    const relatedCount = this.getRelatedCount(props, eventType);
    if (Number.isFinite(relatedCount) && relatedCount > 0) {
      return `Related (${relatedCount})`;
    }
    return 'Related';
  },

  /**
   * Check if event has related cross-type links
   */
  hasRelated(props, eventType) {
    // Check for explicit links
    if (props.parent_event_id) return true;
    if (props.eq_event_id) return true;
    if (props.volcano_id) return true;
    if (props.hurricane_id) return true;
    if (props.related_events && props.related_events.length > 0) return true;

    // Type-specific related data opportunities
    switch (eventType) {
      case 'earthquake':
        // Can link to volcanoes or tsunamis
        return props.year >= 1900;

      case 'tsunami':
        // Can link back to triggering earthquake
        return props.cause === 'Earthquake' || props.cause === 'Volcano';

      case 'volcano':
        // Can link to earthquakes
        return props.year >= 1900;

      default:
        return false;
    }
  },

  buildPopupTutorialHelp(props, eventType) {
    const seqText = this.getSequenceText(props, eventType);
    const relatedText = this.getRelatedText(props, eventType);
    let middleActionHelp = `${seqText} shows the event footprint or progression when available.`;
    if (seqText.startsWith('Aftershocks')) {
      middleActionHelp = `${seqText} follows the earthquake sequence tied to this event.`;
    } else if (seqText.startsWith('Runups')) {
      middleActionHelp = `${seqText} shows recorded tsunami wave impacts tied to this event.`;
    } else if (seqText === 'Track' || seqText === 'Path' || seqText === 'Progression' || seqText === 'Extent') {
      middleActionHelp = `${seqText} steps through how this disaster moved or spread.`;
    }
    return `Details shows structured facts for this disaster. ${middleActionHelp} ${relatedText} shows linked disasters in other hazard families, such as earthquake-to-tsunami connections.`;
  },

  getSequencePreview(props, eventType) {
    let count = null;
    let noun = 'events';
    const actionLabel = this.getSequenceText(props, eventType);
    let description = `${actionLabel} loads a focused map view for this disaster.`;

    switch (eventType) {
      case 'earthquake':
        count = Math.max(1, props.aftershock_count || 0);
        noun = props.aftershock_count > 0 ? 'aftershocks' : 'impact event';
        description = props.aftershock_count > 0
          ? 'This loads the mainshock plus linked aftershocks into a focused animation.'
          : 'This loads a focused impact animation for the selected earthquake.';
        break;
      case 'tsunami':
        count = Math.max(1, props.runup_count || 0);
        noun = props.runup_count > 0 ? 'runup observations' : 'impact event';
        description = props.runup_count > 0
          ? 'This loads the tsunami source and recorded runup observations.'
          : 'This loads a focused tsunami impact animation.';
        break;
      case 'tornado':
        count = Math.max(1, props.sequence_count || 0);
        noun = props.sequence_count > 1 ? 'tornadoes' : 'track view';
        description = props.sequence_count > 1
          ? 'This loads the linked tornado sequence for the same storm system.'
          : 'This loads a focused tornado path or point animation.';
        break;
      case 'wildfire':
        count = props.has_progression ? null : 1;
        noun = props.has_progression ? 'progression animation' : 'impact view';
        description = props.has_progression
          ? 'This loads the wildfire progression animation when daily spread data is available.'
          : 'This loads a focused wildfire impact view.';
        break;
      case 'flood':
        count = 1;
        noun = props.has_geometry ? 'extent animation' : 'impact view';
        description = props.has_geometry
          ? 'This loads the flood extent animation for the selected event.'
          : 'This loads a focused flood impact view.';
        break;
      case 'volcano':
        count = 1;
        noun = 'focused event view';
        description = 'This loads a focused volcano impact view.';
        break;
      case 'landslide':
      default:
        count = 1;
        noun = 'focused event view';
        break;
    }

    const warning = count != null && count >= 5000
      ? `This is a very large load: ${count.toLocaleString()} ${noun}.`
      : null;

    return { count, noun, actionLabel, description, warning };
  },

  buildSequenceConfirmPopup(props, eventType) {
    const color = this.colors[eventType] || this.colors.generic;
    const title = this.getTitle(props, eventType);
    const tutorialHelp = this.buildPopupTutorialHelp(props, eventType);
    const preview = this.getSequencePreview(props, eventType);
    const countText = preview.count != null
      ? `${preview.count.toLocaleString()} ${preview.noun}`
      : preview.noun;

    return `
      <div class="disaster-popup popup-sequence" data-type="${eventType}" data-id="${props.event_id || ''}">
        <div class="popup-header-detail" style="border-left: 4px solid ${color}">
          <button class="popup-back" data-action="back">&lt; Back</button>
          <span class="popup-title-detail">${preview.actionLabel}</span>
          <div class="popup-tutorial-wrap">
            <button class="popup-tutorial-tip" type="button" aria-label="Disaster popup help">?</button>
            <div class="popup-tutorial-tooltip">${tutorialHelp}</div>
          </div>
        </div>

        <div class="sequence-summary">
          <strong>${title}</strong>
          <div class="seq-count">${countText}</div>
        </div>

        <div class="related-empty popup-load-summary">${preview.description}</div>
        ${preview.warning ? `<div class="popup-load-warning">${preview.warning}</div>` : ''}

        <div class="popup-actions">
          <button class="popup-btn btn-sequence" data-action="load-sequence">
            Load ${preview.actionLabel}
          </button>
        </div>
      </div>
    `;
  },

  buildRelatedConfirmPopup(props, eventType, relatedData) {
    const icon = this.icons[eventType] || this.icons.generic;
    const color = this.colors[eventType] || this.colors.generic;
    const title = this.getTitle(props, eventType);
    const tutorialHelp = this.buildPopupTutorialHelp(props, eventType);
    const count = relatedData?.related?.length ?? relatedData?.count ?? 0;
    const message = relatedData?.message || null;

    let statusHtml = '<div class="related-empty popup-load-summary">Checking for cross-disaster links...</div>';
    let actionHtml = '';

    if (relatedData) {
      if (count > 0) {
        statusHtml = `<div class="related-empty popup-load-summary">${count.toLocaleString()} linked disasters from other hazard families found for this event.</div>`;
        actionHtml = `
          <div class="popup-actions">
            <button class="popup-btn btn-sequence" data-action="view-chain">
              View Linked Chain
            </button>
            <button class="popup-btn btn-related" data-action="load-related">
              Open Linked Disasters
            </button>
          </div>
        `;
      } else {
        statusHtml = `<div class="related-empty popup-load-summary">${message || 'No cross-disaster links found.'}</div>`;
      }
    }

    return `
      <div class="disaster-popup popup-related" data-type="${eventType}" data-id="${props.event_id || ''}">
        <div class="popup-header-detail" style="border-left: 4px solid ${color}">
          <button class="popup-back" data-action="back">&lt; Back</button>
          <span class="popup-title-detail">Cross-Disaster Links</span>
          <div class="popup-tutorial-wrap">
            <button class="popup-tutorial-tip" type="button" aria-label="Disaster popup help">?</button>
            <div class="popup-tutorial-tooltip">${tutorialHelp}</div>
          </div>
        </div>

        <div class="related-primary">
          <span class="related-icon" style="background: ${color}">${icon}</span>
          <div class="related-info">
            <div class="related-title">${title}</div>
            <div class="related-subtitle">${this.getSubtitle(props, eventType)}</div>
          </div>
        </div>

        ${statusHtml}
        ${actionHtml}
      </div>
    `;
  },

  /**
   * Build the basic popup HTML
   */
  buildBasicPopup(props, eventType) {
    const icon = this.icons[eventType] || this.icons.generic;
    const color = this.colors[eventType] || this.colors.generic;
    const title = this.getTitle(props, eventType);
    const subtitle = this.getSubtitle(props, eventType);

    const power = this.formatPower(props, eventType);
    const time = this.formatTime(props, eventType);
    const impact = this.formatImpact(props, eventType);
    const tutorialHelp = this.buildPopupTutorialHelp(props, eventType);

    const hasSeq = this.hasSequence(props, eventType);
    const hasRel = this.hasRelated(props, eventType);
    const seqText = this.getSequenceText(props, eventType);
    const relatedText = this.getRelatedText(props, eventType);

    // Build HTML
    let html = `
      <div class="disaster-popup" data-type="${eventType}" data-id="${props.event_id || ''}">
        <div class="popup-header" style="border-left: 4px solid ${color}">
          <span class="popup-icon" style="background: ${color}">${icon}</span>
          <div class="popup-title-group">
            <div class="popup-title">${title}</div>
            <div class="popup-subtitle">${subtitle}</div>
          </div>
          <div class="popup-tutorial-wrap">
            <button class="popup-tutorial-tip" type="button" aria-label="Disaster popup help">?</button>
            <div class="popup-tutorial-tooltip">${tutorialHelp}</div>
          </div>
        </div>

        <div class="popup-stats">
          <div class="stat-card">
            <div class="stat-label">${power.label}</div>
            <div class="stat-value">${power.value}</div>
            ${power.detail ? `<div class="stat-detail">${power.detail}</div>` : ''}
          </div>
          <div class="stat-card">
            <div class="stat-label">${time.label}</div>
            <div class="stat-value">${time.value}</div>
            ${time.detail ? `<div class="stat-detail">${time.detail}</div>` : ''}
          </div>
          <div class="stat-card">
            <div class="stat-label">${impact.label}</div>
            <div class="stat-value">${impact.value}</div>
            ${impact.detail ? `<div class="stat-detail">${impact.detail}</div>` : ''}
          </div>
        </div>

        <div class="popup-actions">
          <button class="popup-btn btn-details" data-action="details">
            Details
          </button>
          <button class="popup-btn btn-sequence${hasSeq ? '' : ' disabled'}" data-action="sequence" ${hasSeq ? '' : 'disabled'}>
            ${seqText}
          </button>
          <button class="popup-btn btn-related${hasRel ? '' : ' disabled'}" data-action="related" ${hasRel ? '' : 'disabled'}>
            ${relatedText}
          </button>
        </div>
      </div>
    `;

    return html;
  },

  /**
   * Build the detail view popup HTML
   */
  buildDetailPopup(props, eventType, detailData) {
    const icon = this.icons[eventType] || this.icons.generic;
    const color = this.colors[eventType] || this.colors.generic;
    const title = this.getTitle(props, eventType);
    const tutorialHelp = this.buildPopupTutorialHelp(props, eventType);

    // Merge props with detail data
    const data = { ...props, ...detailData };

    let html = `
      <div class="disaster-popup popup-detail" data-type="${eventType}" data-id="${props.event_id || ''}">
        <div class="popup-header-detail" style="border-left: 4px solid ${color}">
          <button class="popup-back" data-action="back">&lt; Back</button>
          <span class="popup-title-detail">${title}</span>
          <div class="popup-tutorial-wrap">
            <button class="popup-tutorial-tip" type="button" aria-label="Disaster popup help">?</button>
            <div class="popup-tutorial-tooltip">${tutorialHelp}</div>
          </div>
        </div>

        <div class="popup-tabs">
          <button class="tab-btn active" data-tab="overview">Overview</button>
          <button class="tab-btn" data-tab="impact">Impact</button>
          <button class="tab-btn" data-tab="technical">Technical</button>
          <button class="tab-btn" data-tab="source">Source</button>
        </div>

        <div class="tab-content active" data-tab="overview">
          ${this.buildOverviewTab(data, eventType)}
        </div>
        <div class="tab-content" data-tab="impact">
          ${this.buildImpactTab(data, eventType)}
        </div>
        <div class="tab-content" data-tab="technical">
          ${this.buildTechnicalTab(data, eventType)}
        </div>
        <div class="tab-content" data-tab="source">
          ${this.buildSourceTab(data, eventType)}
        </div>

        <div class="popup-actions">
          <button class="popup-btn btn-sequence" data-action="sequence">
            ${this.getSequenceText(props, eventType)}
          </button>
          ${eventType === 'volcano' && (props.route_focus_anchor || props.history_context_key) ? `
          <button class="popup-btn btn-history" data-action="history">
            History
          </button>
          ` : ''}
          <button class="popup-btn btn-related" data-action="related">
            ${this.getRelatedText(props, eventType)}
          </button>
        </div>
      </div>
    `;

    return html;
  },

  /**
   * Build overview tab content
   */
  buildOverviewTab(data, eventType) {
    const lines = [];

    // Location
    if (data.place) {
      lines.push(`<div class="detail-row"><span class="detail-label">Location:</span> ${data.place}</div>`);
    } else if (data.location) {
      lines.push(`<div class="detail-row"><span class="detail-label">Location:</span> ${data.location}</div>`);
    }
    if (data.country) {
      lines.push(`<div class="detail-row"><span class="detail-label">Country:</span> ${data.country}</div>`);
    }
    if (data.region) {
      lines.push(`<div class="detail-row"><span class="detail-label">Region:</span> ${data.region}</div>`);
    }

    // Coordinates
    if (data.latitude != null && data.longitude != null) {
      lines.push(`<div class="detail-row"><span class="detail-label">Coordinates:</span> ${data.latitude.toFixed(4)}, ${data.longitude.toFixed(4)}</div>`);
    }

    // Date/time - show full range if available
    if (data.start_date && data.end_date) {
      const range = this.formatDateRange(data.start_date, data.end_date);
      if (range) {
        lines.push(`<div class="detail-row"><span class="detail-label">Active Period:</span> ${range}</div>`);
      }
    } else if (data.timestamp && data.end_timestamp) {
      const range = this.formatDateRange(data.timestamp, data.end_timestamp);
      if (range) {
        lines.push(`<div class="detail-row"><span class="detail-label">Active Period:</span> ${range}</div>`);
      }
    } else if (data.timestamp) {
      const dateStr = this.formatDate(data.timestamp);
      if (dateStr) {
        lines.push(`<div class="detail-row"><span class="detail-label">Date:</span> ${dateStr}</div>`);
      }
    } else if (data.year) {
      const yr = data.year < 0 ? `${Math.abs(data.year)} BCE` : data.year;
      lines.push(`<div class="detail-row"><span class="detail-label">Year:</span> ${yr}</div>`);
    }

    // Duration (explicit or calculated)
    if (data.duration_days != null && data.duration_days > 0) {
      lines.push(`<div class="detail-row"><span class="detail-label">Duration:</span> ${data.duration_days} days</div>`);
    }

    // Type-specific overview data
    switch (eventType) {
      case 'earthquake':
        if (data.is_mainshock === true) {
          lines.push(`<div class="detail-row"><span class="detail-label">Type:</span> Mainshock</div>`);
        } else if (data.is_mainshock === false) {
          lines.push(`<div class="detail-row"><span class="detail-label">Type:</span> Aftershock</div>`);
        }
        if (data.aftershock_count > 0) {
          lines.push(`<div class="detail-row"><span class="detail-label">Aftershocks:</span> ${data.aftershock_count}</div>`);
        }
        break;

      case 'tsunami':
        if (data.cause) {
          lines.push(`<div class="detail-row"><span class="detail-label">Cause:</span> ${data.cause}</div>`);
        }
        if (data.runup_count > 0) {
          lines.push(`<div class="detail-row"><span class="detail-label">Runup Count:</span> ${data.runup_count} observations</div>`);
        }
        break;

      case 'volcano':
        if (data.volcano_name) {
          lines.push(`<div class="detail-row"><span class="detail-label">Volcano:</span> ${data.volcano_name}</div>`);
        }
        if (data.activity_type) {
          lines.push(`<div class="detail-row"><span class="detail-label">Activity:</span> ${data.activity_type}</div>`);
        }
        if (data.is_ongoing) {
          lines.push(`<div class="detail-row"><span class="detail-label">Status:</span> Ongoing eruption</div>`);
        }
        break;

      case 'hurricane':
      case 'tropical_storm':
        if (data.name) {
          lines.push(`<div class="detail-row"><span class="detail-label">Storm Name:</span> ${data.name}</div>`);
        }
        if (data.basin) {
          const basinNames = { NA: 'North Atlantic', EP: 'East Pacific', WP: 'West Pacific', NI: 'North Indian', SI: 'South Indian', SP: 'South Pacific' };
          lines.push(`<div class="detail-row"><span class="detail-label">Basin:</span> ${basinNames[data.basin] || data.basin}</div>`);
        }
        if (data.made_landfall === true) {
          lines.push(`<div class="detail-row"><span class="detail-label">Landfall:</span> Yes</div>`);
        } else if (data.made_landfall === false) {
          lines.push(`<div class="detail-row"><span class="detail-label">Landfall:</span> No (remained at sea)</div>`);
        }
        if (data.num_positions > 0) {
          lines.push(`<div class="detail-row"><span class="detail-label">Track Points:</span> ${data.num_positions}</div>`);
        }
        break;

      case 'tornado':
        if (data.tornado_scale) {
          const desc = this.getTornadoDescription(data.tornado_scale);
          lines.push(`<div class="detail-row"><span class="detail-label">Scale:</span> ${data.tornado_scale}${desc ? ` (${desc})` : ''}</div>`);
        }
        if (data.sequence_count > 1) {
          lines.push(`<div class="detail-row"><span class="detail-label">Outbreak:</span> Part of ${data.sequence_count}-tornado sequence</div>`);
        }
        break;

      case 'wildfire':
        if (data.land_cover) {
          lines.push(`<div class="detail-row"><span class="detail-label">Vegetation:</span> ${data.land_cover}</div>`);
        }
        if (data.has_progression) {
          lines.push(`<div class="detail-row"><span class="detail-label">Progression:</span> Daily spread data available</div>`);
        }
        break;

      case 'flood':
        if (data.severity != null) {
          const severityLabels = { 1: 'Minor', 2: 'Moderate', 3: 'Severe' };
          lines.push(`<div class="detail-row"><span class="detail-label">Severity:</span> ${severityLabels[data.severity] || data.severity}</div>`);
        }
        if (data.has_geometry) {
          const extentLabel = data.source === 'GFD'
            ? 'Satellite-observed flood footprint available'
            : 'Affected region outline available (not a water extent)';
          lines.push(`<div class="detail-row"><span class="detail-label">Extent:</span> ${extentLabel}</div>`);
        }
        break;

      case 'landslide':
        if (data.source) {
          lines.push(`<div class="detail-row"><span class="detail-label">Source:</span> ${data.source}</div>`);
        }
        if (data.injuries != null && data.injuries > 0) {
          lines.push(`<div class="detail-row"><span class="detail-label">Injuries:</span> ${data.injuries.toLocaleString()}</div>`);
        }
        if (data.missing != null && data.missing > 0) {
          lines.push(`<div class="detail-row"><span class="detail-label">Missing:</span> ${data.missing.toLocaleString()}</div>`);
        }
        break;
    }

    return lines.join('\n') || '<div class="detail-empty">No overview data available</div>';
  },

  /**
   * Format currency value
   */
  formatCurrency(value) {
    if (value == null || value <= 0) return null;
    if (value >= 1e12) return `$${(value / 1e12).toFixed(1)}T`;
    if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
    if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
    if (value >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
    return `$${value.toLocaleString()}`;
  },

  /**
   * Build impact tab content
   */
  buildImpactTab(data, eventType) {
    const lines = [];

    // Human impact section
    let hasHumanImpact = false;

    // Deaths - check multiple field names
    const deaths = data.deaths || data.deaths_direct;
    if (deaths != null && deaths > 0) {
      lines.push(`<div class="detail-row impact-deaths"><span class="detail-label">Deaths:</span> ${deaths.toLocaleString()}</div>`);
      hasHumanImpact = true;
    }

    // Indirect deaths (for tornadoes)
    if (data.deaths_indirect != null && data.deaths_indirect > 0) {
      lines.push(`<div class="detail-row"><span class="detail-label">Indirect Deaths:</span> ${data.deaths_indirect.toLocaleString()}</div>`);
      hasHumanImpact = true;
    }

    // Injuries - check multiple field names
    const injuries = data.injuries || data.injuries_direct;
    if (injuries != null && injuries > 0) {
      lines.push(`<div class="detail-row"><span class="detail-label">Injuries:</span> ${injuries.toLocaleString()}</div>`);
      hasHumanImpact = true;
    }

    // Indirect injuries (for tornadoes)
    if (data.injuries_indirect != null && data.injuries_indirect > 0) {
      lines.push(`<div class="detail-row"><span class="detail-label">Indirect Injuries:</span> ${data.injuries_indirect.toLocaleString()}</div>`);
      hasHumanImpact = true;
    }

    // Displaced population
    const displaced = data.displaced || data.displaced_count;
    if (displaced != null && displaced > 0) {
      lines.push(`<div class="detail-row"><span class="detail-label">Displaced:</span> ${this.formatLargeNumber(displaced)} people</div>`);
      hasHumanImpact = true;
    }

    // Missing persons
    if (data.missing != null && data.missing > 0) {
      lines.push(`<div class="detail-row"><span class="detail-label">Missing:</span> ${this.formatLargeNumber(data.missing)} people</div>`);
      hasHumanImpact = true;
    }

    // Houses destroyed
    if (data.houses_destroyed != null && data.houses_destroyed > 0) {
      lines.push(`<div class="detail-row"><span class="detail-label">Houses Destroyed:</span> ${this.formatLargeNumber(data.houses_destroyed)}</div>`);
      hasHumanImpact = true;
    }

    // Houses damaged
    if (data.houses_damaged != null && data.houses_damaged > 0) {
      lines.push(`<div class="detail-row"><span class="detail-label">Houses Damaged:</span> ${this.formatLargeNumber(data.houses_damaged)}</div>`);
      hasHumanImpact = true;
    }

    // Add separator if we have human impact
    if (hasHumanImpact && (data.damage_usd || data.damage_property || data.damage_crops || data.damage_millions)) {
      lines.push(`<div class="detail-separator"></div>`);
    }

    // Economic impact section
    // Property damage - check multiple field names
    const propertyDamage = data.damage_property || data.damage_usd;
    const propertyStr = this.formatCurrency(propertyDamage);
    if (propertyStr) {
      lines.push(`<div class="detail-row"><span class="detail-label">Property Damage:</span> ${propertyStr}</div>`);
    }

    // Damage in millions (older records)
    if (data.damage_millions != null && data.damage_millions > 0 && !propertyDamage) {
      lines.push(`<div class="detail-row"><span class="detail-label">Damage:</span> $${data.damage_millions.toLocaleString()}M</div>`);
    }

    // Crop damage (for tornadoes)
    const cropStr = this.formatCurrency(data.damage_crops);
    if (cropStr) {
      lines.push(`<div class="detail-row"><span class="detail-label">Crop Damage:</span> ${cropStr}</div>`);
    }

    // Physical extent section
    if (lines.length > 0 && (data.area_km2 || data.burned_acres || data.felt_radius_km)) {
      lines.push(`<div class="detail-separator"></div>`);
    }

    // Area affected
    if (data.area_km2 != null && data.area_km2 > 0) {
      const areaStr = data.area_km2 >= 1000 ? `${(data.area_km2/1000).toFixed(1)}K km2` : `${Math.round(data.area_km2)} km2`;
      lines.push(`<div class="detail-row"><span class="detail-label">Area Affected:</span> ${areaStr}</div>`);
    }

    // Burned acres (for wildfires)
    if (data.burned_acres != null && data.burned_acres > 0) {
      const acresStr = data.burned_acres >= 1000 ? `${(data.burned_acres/1000).toFixed(1)}K acres` : `${Math.round(data.burned_acres)} acres`;
      lines.push(`<div class="detail-row"><span class="detail-label">Burned Area:</span> ${acresStr}</div>`);
    }

    // Felt radius (for earthquakes)
    if (data.felt_radius_km != null && data.felt_radius_km > 0) {
      const feltStr = data.felt_radius_km >= 1000 ? `${(data.felt_radius_km/1000).toFixed(1)}K km` : `${Math.round(data.felt_radius_km)} km`;
      lines.push(`<div class="detail-row"><span class="detail-label">Felt Radius:</span> ${feltStr}</div>`);
    }

    // Damage radius
    if (data.damage_radius_km != null && data.damage_radius_km > 0) {
      lines.push(`<div class="detail-row"><span class="detail-label">Damage Radius:</span> ${Math.round(data.damage_radius_km)} km</div>`);
    }

    // Max runup distance (for tsunamis)
    if (data.max_runup_dist_km != null && data.max_runup_dist_km > 0) {
      lines.push(`<div class="detail-row"><span class="detail-label">Max Reach:</span> ${Math.round(data.max_runup_dist_km)} km</div>`);
    }

    // Tornado path
    const pathLen = data.path_length_miles || data.tornado_length_mi;
    const pathWidth = data.path_width_yards || data.tornado_width_yd;
    if (pathLen != null && pathLen > 0) {
      lines.push(`<div class="detail-row"><span class="detail-label">Path Length:</span> ${pathLen.toFixed(1)} miles</div>`);
    }
    if (pathWidth != null && pathWidth > 0) {
      lines.push(`<div class="detail-row"><span class="detail-label">Path Width:</span> ${pathWidth} yards</div>`);
    }

    return lines.join('\n') || '<div class="detail-empty">No impact data recorded</div>';
  },

  /**
   * Build technical tab content
   */
  buildTechnicalTab(data, eventType) {
    const lines = [];

    switch (eventType) {
      case 'earthquake':
        if (data.magnitude != null) {
          lines.push(`<div class="detail-row"><span class="detail-label">Magnitude:</span> ${data.magnitude.toFixed(1)} Mw</div>`);
        }
        if (data.depth_km != null) {
          lines.push(`<div class="detail-row"><span class="detail-label">Depth:</span> ${data.depth_km.toFixed(1)} km</div>`);
        }
        if (data.intensity != null) {
          lines.push(`<div class="detail-row"><span class="detail-label">Intensity:</span> ${data.intensity} (MMI)</div>`);
        }
        if (data.felt_radius_km != null) {
          const feltStr = data.felt_radius_km >= 1000 ? `${(data.felt_radius_km/1000).toFixed(1)}K km` : `${Math.round(data.felt_radius_km)} km`;
          lines.push(`<div class="detail-row"><span class="detail-label">Felt Radius:</span> ${feltStr}</div>`);
        }
        if (data.damage_radius_km != null) {
          lines.push(`<div class="detail-row"><span class="detail-label">Damage Radius:</span> ${Math.round(data.damage_radius_km)} km</div>`);
        }
        // Sequence info
        if (data.mainshock_id) {
          lines.push(`<div class="detail-row"><span class="detail-label">Mainshock ID:</span> ${data.mainshock_id}</div>`);
        }
        if (data.sequence_id) {
          lines.push(`<div class="detail-row"><span class="detail-label">Sequence ID:</span> ${data.sequence_id}</div>`);
        }
        // Related events
        if (data.tsunami_event_id) {
          lines.push(`<div class="detail-row"><span class="detail-label">Triggered Tsunami:</span> ${data.tsunami_event_id}</div>`);
        }
        if (data.volcano_event_id) {
          lines.push(`<div class="detail-row"><span class="detail-label">Related Volcano:</span> ${data.volcano_event_id}</div>`);
        }
        break;

      case 'tsunami':
        if (data.eq_magnitude != null) {
          lines.push(`<div class="detail-row"><span class="detail-label">Triggering EQ:</span> M${data.eq_magnitude.toFixed(1)}</div>`);
        }
        if (data.max_water_height_m != null) {
          lines.push(`<div class="detail-row"><span class="detail-label">Max Wave Height:</span> ${data.max_water_height_m.toFixed(1)} m</div>`);
        }
        if (data.intensity != null) {
          lines.push(`<div class="detail-row"><span class="detail-label">Tsunami Intensity:</span> ${data.intensity}</div>`);
        }
        if (data.runup_count != null && data.runup_count > 0) {
          lines.push(`<div class="detail-row"><span class="detail-label">Runup Observations:</span> ${data.runup_count}</div>`);
        }
        if (data.max_runup_dist_km != null && data.max_runup_dist_km > 0) {
          lines.push(`<div class="detail-row"><span class="detail-label">Furthest Runup:</span> ${Math.round(data.max_runup_dist_km)} km</div>`);
        }
        // Related events
        if (data.eq_event_id) {
          lines.push(`<div class="detail-row"><span class="detail-label">Source EQ ID:</span> ${data.eq_event_id}</div>`);
        }
        if (data.volcano_name) {
          lines.push(`<div class="detail-row"><span class="detail-label">Source Volcano:</span> ${data.volcano_name}</div>`);
        }
        break;

      case 'volcano':
        if (data.VEI != null) {
          const veiDesc = ['Non-explosive', 'Gentle', 'Explosive', 'Severe', 'Cataclysmic', 'Paroxysmal', 'Colossal', 'Super-colossal', 'Mega-colossal'];
          lines.push(`<div class="detail-row"><span class="detail-label">VEI:</span> ${data.VEI}${veiDesc[data.VEI] ? ` (${veiDesc[data.VEI]})` : ''}</div>`);
        }
        if (data.activity_type) {
          lines.push(`<div class="detail-row"><span class="detail-label">Activity Type:</span> ${data.activity_type}</div>`);
        }
        if (data.activity_area) {
          lines.push(`<div class="detail-row"><span class="detail-label">Activity Area:</span> ${data.activity_area}</div>`);
        }
        if (data.volcano_number) {
          lines.push(`<div class="detail-row"><span class="detail-label">Volcano Number:</span> ${data.volcano_number}</div>`);
        }
        if (data.felt_radius_km != null && data.felt_radius_km > 0) {
          lines.push(`<div class="detail-row"><span class="detail-label">Felt Radius:</span> ${Math.round(data.felt_radius_km)} km</div>`);
        }
        if (data.damage_radius_km != null && data.damage_radius_km > 0) {
          lines.push(`<div class="detail-row"><span class="detail-label">Damage Radius:</span> ${Math.round(data.damage_radius_km)} km</div>`);
        }
        // Related events
        if (data.earthquake_event_ids) {
          lines.push(`<div class="detail-row"><span class="detail-label">Related EQs:</span> ${data.earthquake_event_ids}</div>`);
        }
        if (data.tsunami_event_ids) {
          lines.push(`<div class="detail-row"><span class="detail-label">Triggered Tsunamis:</span> ${data.tsunami_event_ids}</div>`);
        }
        break;

      case 'tornado':
        if (data.tornado_scale) {
          const desc = this.getTornadoDescription(data.tornado_scale);
          lines.push(`<div class="detail-row"><span class="detail-label">Scale:</span> ${data.tornado_scale}${desc ? ` (${desc})` : ''}</div>`);
        }
        if (data.magnitude != null) {
          lines.push(`<div class="detail-row"><span class="detail-label">Magnitude:</span> ${data.magnitude}</div>`);
        }
        const pathLen = data.path_length_miles || data.tornado_length_mi;
        if (pathLen != null && pathLen > 0) {
          lines.push(`<div class="detail-row"><span class="detail-label">Path Length:</span> ${pathLen.toFixed(1)} miles</div>`);
        }
        const pathWidth = data.path_width_yards || data.tornado_width_yd;
        if (pathWidth != null && pathWidth > 0) {
          lines.push(`<div class="detail-row"><span class="detail-label">Path Width:</span> ${pathWidth} yards</div>`);
        }
        // End coordinates
        if (data.end_latitude != null && data.end_longitude != null) {
          lines.push(`<div class="detail-row"><span class="detail-label">End Point:</span> ${data.end_latitude.toFixed(4)}, ${data.end_longitude.toFixed(4)}</div>`);
        }
        // Sequence info
        if (data.sequence_count > 1) {
          lines.push(`<div class="detail-row"><span class="detail-label">Outbreak Size:</span> ${data.sequence_count} tornadoes</div>`);
        }
        if (data.sequence_position != null) {
          lines.push(`<div class="detail-row"><span class="detail-label">Sequence Position:</span> #${data.sequence_position}</div>`);
        }
        break;

      case 'wildfire':
        if (data.area_km2 != null && data.area_km2 > 0) {
          const areaStr = data.area_km2 >= 1000 ? `${(data.area_km2/1000).toFixed(1)}K km2` : `${data.area_km2.toFixed(1)} km2`;
          lines.push(`<div class="detail-row"><span class="detail-label">Area:</span> ${areaStr}</div>`);
        }
        if (data.burned_acres != null && data.burned_acres > 0) {
          const acresStr = data.burned_acres >= 1000 ? `${(data.burned_acres/1000).toFixed(1)}K acres` : `${Math.round(data.burned_acres)} acres`;
          lines.push(`<div class="detail-row"><span class="detail-label">Burned Acres:</span> ${acresStr}</div>`);
        }
        if (data.duration_days != null && data.duration_days > 0) {
          lines.push(`<div class="detail-row"><span class="detail-label">Duration:</span> ${data.duration_days} days</div>`);
        }
        if (data.land_cover) {
          lines.push(`<div class="detail-row"><span class="detail-label">Vegetation:</span> ${data.land_cover}</div>`);
        }
        if (data.has_progression) {
          lines.push(`<div class="detail-row"><span class="detail-label">Progression Data:</span> Available</div>`);
        }
        // Location assignment data
        if (data.loc_id) {
          lines.push(`<div class="detail-row"><span class="detail-label">Location ID:</span> ${data.loc_id}</div>`);
        }
        if (data.parent_loc_id) {
          lines.push(`<div class="detail-row"><span class="detail-label">Parent Region:</span> ${data.parent_loc_id}</div>`);
        }
        if (data.iso3) {
          lines.push(`<div class="detail-row"><span class="detail-label">Country:</span> ${data.iso3}</div>`);
        }
        break;

      case 'hurricane':
      case 'tropical_storm':
        if (data.max_category) {
          lines.push(`<div class="detail-row"><span class="detail-label">Max Category:</span> ${data.max_category}</div>`);
        }
        if (data.max_wind_kt != null) {
          lines.push(`<div class="detail-row"><span class="detail-label">Max Wind:</span> ${data.max_wind_kt} kt (${Math.round(data.max_wind_kt * 1.15)} mph)</div>`);
        }
        if (data.min_pressure_mb != null) {
          lines.push(`<div class="detail-row"><span class="detail-label">Min Pressure:</span> ${data.min_pressure_mb} mb</div>`);
        }
        if (data.basin) {
          const basinNames = { NA: 'North Atlantic', EP: 'East Pacific', WP: 'West Pacific', NI: 'North Indian', SI: 'South Indian', SP: 'South Pacific' };
          lines.push(`<div class="detail-row"><span class="detail-label">Basin:</span> ${basinNames[data.basin] || data.basin}</div>`);
        }
        if (data.subbasin) {
          lines.push(`<div class="detail-row"><span class="detail-label">Sub-basin:</span> ${data.subbasin}</div>`);
        }
        if (data.source_agency) {
          lines.push(`<div class="detail-row"><span class="detail-label">Source Agency:</span> ${data.source_agency}</div>`);
        }
        if (data.has_wind_radii) {
          lines.push(`<div class="detail-row"><span class="detail-label">Wind Radii:</span> Available</div>`);
        }
        break;

      case 'flood':
        if (data.severity != null) {
          const severityLabels = { 1: 'Minor (1)', 2: 'Moderate (2)', 3: 'Severe (3)' };
          lines.push(`<div class="detail-row"><span class="detail-label">Severity:</span> ${severityLabels[data.severity] || data.severity}</div>`);
        }
        if (data.area_km2 != null && data.area_km2 > 0) {
          const areaStr = data.area_km2 >= 1000 ? `${(data.area_km2/1000).toFixed(1)}K km2` : `${Math.round(data.area_km2)} km2`;
          lines.push(`<div class="detail-row"><span class="detail-label">Area:</span> ${areaStr}</div>`);
        }
        if (data.duration_days != null && data.duration_days > 0) {
          lines.push(`<div class="detail-row"><span class="detail-label">Duration:</span> ${data.duration_days} days</div>`);
        }
        if (data.dfo_id) {
          lines.push(`<div class="detail-row"><span class="detail-label">DFO ID:</span> ${data.dfo_id}</div>`);
        }
        if (data.glide_index) {
          lines.push(`<div class="detail-row"><span class="detail-label">GLIDE Index:</span> ${data.glide_index}</div>`);
        }
        if (data.has_geometry) {
          const polyKind = data.source === 'GFD' ? 'Satellite footprint (GFD)' : 'Affected region outline (DFO)';
          lines.push(`<div class="detail-row"><span class="detail-label">Flood Polygon:</span> ${polyKind}</div>`);
        }
        if (data.has_progression) {
          lines.push(`<div class="detail-row"><span class="detail-label">Progression Data:</span> Available</div>`);
        }
        // Location assignment data
        if (data.loc_id) {
          lines.push(`<div class="detail-row"><span class="detail-label">Location ID:</span> ${data.loc_id}</div>`);
        }
        if (data.parent_loc_id) {
          lines.push(`<div class="detail-row"><span class="detail-label">Parent Region:</span> ${data.parent_loc_id}</div>`);
        }
        if (data.iso3) {
          lines.push(`<div class="detail-row"><span class="detail-label">Country:</span> ${data.iso3}</div>`);
        }
        break;

      case 'landslide':
        if (data.source) {
          lines.push(`<div class="detail-row"><span class="detail-label">Data Source:</span> ${data.source}</div>`);
        }
        if (data.source_id) {
          lines.push(`<div class="detail-row"><span class="detail-label">Source ID:</span> ${data.source_id}</div>`);
        }
        if (data.houses_destroyed != null && data.houses_destroyed > 0) {
          lines.push(`<div class="detail-row"><span class="detail-label">Homes Destroyed:</span> ${data.houses_destroyed.toLocaleString()}</div>`);
        }
        if (data.damage_usd != null && data.damage_usd > 0) {
          lines.push(`<div class="detail-row"><span class="detail-label">Damage:</span> ${this.formatCurrency(data.damage_usd)}</div>`);
        }
        if (data.loc_id) {
          lines.push(`<div class="detail-row"><span class="detail-label">Location ID:</span> ${data.loc_id}</div>`);
        }
        break;
    }

    return lines.join('\n') || '<div class="detail-empty">No technical data available</div>';
  },

  /**
   * Build source tab content with clickable links to original data sources
   */
  buildSourceTab(data, eventType) {
    const lines = [];

    // Source URLs by type - most data sources have predictable URL patterns
    const sourceUrlBuilders = {
      earthquake: (id, data) => {
        // USGS IDs (like us7000rnr8, ak2026xxx) link directly to eventpage
        // NOAA-SIG IDs are internal - link to NCEI significant earthquake search
        if (id && !id.startsWith('NOAA-SIG')) {
          return `https://earthquake.usgs.gov/earthquakes/eventpage/${id}`;
        }
        // For NOAA significant earthquakes, link to NCEI search with year filter
        if (data.year) {
          return `https://www.ngdc.noaa.gov/hazel/view/hazards/earthquake/search?minYear=${data.year}&maxYear=${data.year}`;
        }
        return 'https://www.ngdc.noaa.gov/hazel/view/hazards/earthquake/search';
      },
      tsunami: (id, data) => {
        // Our TS IDs preserve the NOAA NCEI tsunami id with zero padding.
        const eventId = String(data.event_id || id || '').trim();
        const eventMatch = eventId.match(/^TS0*(\d+)$/i);
        if (eventMatch) {
          return `https://www.ngdc.noaa.gov/hazel/view/hazards/tsunami/event-more-info/${Number(eventMatch[1])}`;
        }

        // Fallback to NCEI search filtered by year when the NOAA id is absent.
        if (data.year) {
          return `https://www.ngdc.noaa.gov/hazel/view/hazards/tsunami/search?minYear=${data.year}&maxYear=${data.year}`;
        }
        return 'https://www.ngdc.noaa.gov/hazel/view/hazards/tsunami/search';
      },
      volcano: (id, data) => {
        // Smithsonian GVP - volcano_number links to volcano page, eruption_id to eruption
        const vnum = data.volcano_number || data.vnum;
        const eruptionId = data.eruption_id;
        if (vnum && eruptionId) {
          return `https://volcano.si.edu/volcano.cfm?vn=${vnum}&vtab=Eruptions#erupt_${eruptionId}`;
        }
        if (vnum) {
          return `https://volcano.si.edu/volcano.cfm?vn=${vnum}`;
        }
        return 'https://volcano.si.edu/';
      },
      hurricane: (id, data) => {
        if (data.source_page_url || data.source_url) {
          return data.source_page_url || data.source_url;
        }
        // Historical IBTrACS fallback - search by storm name and year works best
        const name = data.name;
        const year = data.year;
        if (name && year) {
          return `https://www.ncei.noaa.gov/products/international-best-track-archive?name=${encodeURIComponent(name)}&year=${year}`;
        }
        const sid = data.storm_id || id;
        if (sid) {
          return `https://www.ncei.noaa.gov/products/international-best-track-archive?sid=${sid}`;
        }
        return 'https://www.ncei.noaa.gov/products/international-best-track-archive';
      },
      tropical_storm: (id, data) => {
        if (data.source_page_url || data.source_url) {
          return data.source_page_url || data.source_url;
        }
        const name = data.name;
        const year = data.year;
        if (name && year) {
          return `https://www.ncei.noaa.gov/products/international-best-track-archive?name=${encodeURIComponent(name)}&year=${year}`;
        }
        return 'https://www.ncei.noaa.gov/products/international-best-track-archive';
      },
      tornado: (id, data) => {
        // NOAA Storm Events Database - search by date and location
        const year = data.year || (data.timestamp ? new Date(data.timestamp).getUTCFullYear() : null);
        if (year) {
          return `https://www.ncdc.noaa.gov/stormevents/choosedates.jsp?staession=false&begyear=${year}&endyear=${year}&eventType=Tornado`;
        }
        return 'https://www.ncdc.noaa.gov/stormevents/';
      },
      wildfire: (id, data) => {
        // NASA FIRMS map centered on fire location
        if (data.latitude && data.longitude) {
          const lat = data.latitude.toFixed(4);
          const lon = data.longitude.toFixed(4);
          return `https://firms.modaps.eosdis.nasa.gov/map/#d:24hrs;@${lon},${lat},10z`;
        }
        return 'https://firms.modaps.eosdis.nasa.gov/map/';
      },
      flood: (id, data) => {
        // Prefer a backend-provided durable link when present.
        if (data.source_page_url || data.source_url) {
          return data.source_page_url || data.source_url;
        }
        // The old floodobservatory.colorado.edu/Archives pages were removed
        // (HTTP 410) in the Jan 2026 DFO site redesign. The versioned Zenodo
        // release is the durable archive for DFO/GFD flood records.
        return 'https://zenodo.org/records/19288171';
      },
      drought: (id, data) => {
        // US Drought Monitor for US events, otherwise general
        const country = data.country || data.iso3;
        if (country === 'USA' || country === 'US') {
          return 'https://droughtmonitor.unl.edu/';
        }
        return 'https://spei.csic.es/map/maps.html';
      },
      landslide: (id, data) => {
        // Source-specific URLs
        const source = data.source;
        if (source === 'NASA_GLC' || source === 'nasa') {
          return 'https://gpm.nasa.gov/landslides/';
        }
        if (source === 'DesInventar' || source === 'desinventar') {
          const country = data.country || data.iso3;
          if (country) {
            return `https://www.desinventar.net/DesInventar/profiletab.jsp?countrycode=${country.toLowerCase()}`;
          }
          return 'https://www.desinventar.net/';
        }
        if (source === 'NOAA') {
          return 'https://www.ncei.noaa.gov/access/monitoring/monthly-report/';
        }
        return 'https://gpm.nasa.gov/landslides/';
      }
    };

    // Default source names
    const defaultSources = {
      earthquake: 'USGS Earthquake Catalog',
      tsunami: 'NOAA NCEI Tsunami Database',
      volcano: 'Smithsonian Global Volcanism Program',
      hurricane: 'IBTrACS',
      tropical_storm: 'IBTrACS',
      tornado: 'NOAA Storm Events Database',
      wildfire: 'NASA FIRMS / Global Fire Atlas',
      flood: 'DFO Flood Observatory',
      drought: 'US Drought Monitor',
      landslide: 'NASA Global Landslide Catalog'
    };

    // Build source URL if available
    const urlBuilder = sourceUrlBuilders[eventType];
    const sourceUrl = urlBuilder ? urlBuilder(data.event_id, data) : null;
    const sourceName = data.source_name || data.source || data.data_source || defaultSources[eventType] || 'Unknown';
    const productUrl = data.source_product_url && data.source_product_url !== sourceUrl
      ? data.source_product_url
      : null;
    const eventId = data.event_id || ((eventType === 'hurricane' || eventType === 'tropical_storm') ? data.storm_id : null);

    // Event ID row - make clickable if we have a URL
    if (eventId) {
      if (sourceUrl) {
        lines.push(`<div class="detail-row"><span class="detail-label">Event ID:</span> <a href="${sourceUrl}" target="_blank" rel="noopener" class="source-link">${eventId}</a></div>`);
      } else {
        lines.push(`<div class="detail-row"><span class="detail-label">Event ID:</span> ${eventId}</div>`);
      }
    }

    // Source row - also make clickable if we have a URL
    if (sourceUrl) {
      lines.push(`<div class="detail-row"><span class="detail-label">Source:</span> <a href="${sourceUrl}" target="_blank" rel="noopener" class="source-link">${sourceName}</a></div>`);
    } else {
      lines.push(`<div class="detail-row"><span class="detail-label">Source:</span> ${sourceName}</div>`);
    }

    if (productUrl) {
      const productLabel = (eventType === 'hurricane' || eventType === 'tropical_storm') ? 'Advisory/Product' : 'Source Product';
      lines.push(`<div class="detail-row"><span class="detail-label">${productLabel}:</span> <a href="${productUrl}" target="_blank" rel="noopener" class="source-link">Open</a></div>`);
    }

    if (data.last_updated) {
      lines.push(`<div class="detail-row"><span class="detail-label">Updated:</span> ${data.last_updated}</div>`);
    }

    return lines.join('\n') || '<div class="detail-empty">No source information</div>';
  },

  /**
   * Build sequence view popup HTML
   */
  buildSequencePopup(props, eventType, sequenceData) {
    const icon = this.icons[eventType] || this.icons.generic;
    const color = this.colors[eventType] || this.colors.generic;
    const title = this.getTitle(props, eventType);
    const tutorialHelp = this.buildPopupTutorialHelp(props, eventType);

    let sequenceList = '';
    let summary = '';

    if (sequenceData && sequenceData.events && sequenceData.events.length > 0) {
      summary = `${sequenceData.events.length} events`;
      sequenceList = sequenceData.events.slice(0, 20).map((evt, idx) => {
        const label = evt.label || `Event ${idx + 1}`;
        const sublabel = evt.timestamp ? new Date(evt.timestamp).toLocaleString() : '';
        return `<div class="sequence-item" data-id="${evt.event_id || idx}">
          <span class="seq-marker">${idx === 0 ? '*' : 'o'}</span>
          <span class="seq-label">${label}</span>
          <span class="seq-sublabel">${sublabel}</span>
        </div>`;
      }).join('\n');

      if (sequenceData.events.length > 20) {
        sequenceList += `<div class="sequence-more">... and ${sequenceData.events.length - 20} more</div>`;
      }
    } else {
      summary = 'Loading...';
      sequenceList = '<div class="sequence-loading">Loading sequence data...</div>';
    }

    let html = `
      <div class="disaster-popup popup-sequence" data-type="${eventType}" data-id="${props.event_id || ''}">
        <div class="popup-header-detail" style="border-left: 4px solid ${color}">
          <button class="popup-back" data-action="back">&lt; Back</button>
          <span class="popup-title-detail">${this.getSequenceText(props, eventType)}</span>
          <div class="popup-tutorial-wrap">
            <button class="popup-tutorial-tip" type="button" aria-label="Disaster popup help">?</button>
            <div class="popup-tutorial-tooltip">${tutorialHelp}</div>
          </div>
        </div>

        <div class="sequence-summary">
          <strong>${title}</strong>
          <div class="seq-count">${summary}</div>
        </div>

        <div class="sequence-list">
          ${sequenceList}
        </div>

        <div class="popup-actions">
          <button class="popup-btn btn-related" data-action="related">
            View Cross-Disaster Links
          </button>
        </div>
      </div>
    `;

    return html;
  },

  /**
   * Build related view popup HTML
   */
  buildRelatedPopup(props, eventType, relatedData) {
    const icon = this.icons[eventType] || this.icons.generic;
    const color = this.colors[eventType] || this.colors.generic;
    const title = this.getTitle(props, eventType);
    const tutorialHelp = this.buildPopupTutorialHelp(props, eventType);

    let relatedList = '';
    const relatedCount = relatedData?.related?.length ?? 0;
    const chainActionHtml = relatedCount > 0
      ? `
        <div class="popup-actions">
          <button class="popup-btn btn-sequence" data-action="view-chain">
            View Linked Chain
          </button>
        </div>
      `
      : '';

    if (relatedData && relatedData.related && relatedData.related.length > 0) {
      relatedList = relatedData.related.map(rel => {
        const relIcon = this.icons[rel.event_type] || this.icons.generic;
        const relColor = this.colors[rel.event_type] || this.colors.generic;
        const relTitle = this.getTitle(rel, rel.event_type);
        const linkType = rel.link_type || 'linked';

        return `<div class="related-item" data-id="${rel.event_id}" data-type="${rel.event_type}" data-loc-id="${rel.loc_id || ''}">
          <span class="related-icon" style="background: ${relColor}">${relIcon}</span>
          <div class="related-info">
            <div class="related-title">${relTitle}</div>
            <div class="related-link-type">${linkType}</div>
          </div>
        </div>`;
      }).join('\n');
    } else {
      const emptyMessage = relatedData?.message || 'No cross-disaster links found';
      relatedList = `<div class="related-empty">${emptyMessage}</div>`;
    }

    let html = `
      <div class="disaster-popup popup-related" data-type="${eventType}" data-id="${props.event_id || ''}">
        <div class="popup-header-detail" style="border-left: 4px solid ${color}">
          <button class="popup-back" data-action="back">&lt; Back</button>
          <span class="popup-title-detail">Cross-Disaster Links</span>
          <div class="popup-tutorial-wrap">
            <button class="popup-tutorial-tip" type="button" aria-label="Disaster popup help">?</button>
            <div class="popup-tutorial-tooltip">${tutorialHelp}</div>
          </div>
        </div>

        <div class="related-primary">
          <span class="related-icon" style="background: ${color}">${icon}</span>
          <div class="related-info">
            <div class="related-title">${title}</div>
            <div class="related-subtitle">${this.getSubtitle(props, eventType)}</div>
          </div>
        </div>

        <div class="related-chain-label">Cross-disaster chain:</div>
        ${chainActionHtml}

        <div class="related-list">
          ${relatedList}
        </div>

        <div class="popup-footer">
          Click any linked event to open its disaster view
        </div>
      </div>
    `;

    return html;
  },

  buildHistoryConfirmPopup(props, eventType, historyData) {
    const color = this.colors[eventType] || this.colors.generic;
    const title = this.getTitle(props, eventType);
    const subtitle = this.getSubtitle(props, eventType);
    const summary = historyData
      ? `${historyData.events?.length || 0} eruptions found`
      : 'Loading eruption history...';

    return `
      <div class="disaster-popup popup-related" data-type="${eventType}" data-id="${props.event_id || ''}">
        <div class="popup-header-detail" style="border-left: 4px solid ${color}">
          <button class="popup-back" data-action="back">&lt; Back</button>
          <span class="popup-title-detail">Volcano History</span>
        </div>

        <div class="related-primary">
          <span class="related-icon" style="background: ${color}">${this.icons[eventType] || this.icons.generic}</span>
          <div class="related-info">
            <div class="related-title">${title}</div>
            <div class="related-subtitle">${subtitle}</div>
          </div>
        </div>

        <div class="sequence-summary">
          <div class="seq-count">${summary}</div>
        </div>
      </div>
    `;
  },

  buildHistoryPopup(props, eventType, historyData) {
    const color = this.colors[eventType] || this.colors.generic;
    const title = this.getTitle(props, eventType);
    const events = Array.isArray(historyData?.events) ? historyData.events : [];

    const rows = events.length
      ? events.map((evt, idx) => {
          const eventId = String(evt.event_id || '').trim();
          const year = evt.year != null ? evt.year : '';
          const timestamp = evt.timestamp ? this.formatDate(evt.timestamp) : '';
          const vei = evt.VEI != null ? `VEI ${evt.VEI}` : 'VEI unknown';
          const ongoing = evt.is_ongoing === true || evt.is_ongoing === 'true' ? 'ongoing' : '';
          const labelBits = [timestamp || year, vei, ongoing].filter(Boolean).join(' · ');
          const accent = this.getVolcanoHistoryColor(evt.VEI);
          return `<div class="sequence-item history-item" data-id="${eventId}" data-history-index="${idx}" style="border-left:3px solid ${accent}">
            <span class="seq-marker" style="color:${accent}">V</span>
            <span class="seq-label">${eventId || `Eruption ${idx + 1}`}</span>
            <span class="seq-sublabel" style="color:${accent}">${labelBits}</span>
          </div>`;
        }).join('\n')
      : '<div class="related-empty">No historical eruptions found for this volcano anchor.</div>';

    return `
      <div class="disaster-popup popup-sequence" data-type="${eventType}" data-id="${props.event_id || ''}">
        <div class="popup-header-detail" style="border-left: 4px solid ${color}">
          <button class="popup-back" data-action="back">&lt; Back</button>
          <span class="popup-title-detail">Volcano History</span>
        </div>

        <div class="sequence-summary">
          <strong>${title}</strong>
          <div class="seq-count">${events.length} eruptions from this volcano</div>
        </div>

        <div class="sequence-list">
          ${rows}
        </div>

        <div class="popup-footer">
          Click any eruption to open that event. For the full historical timeline and broader context, use Explore mode.
        </div>
      </div>
    `;
  },

  buildEarthquakeSequenceConfirmPopup(props, eventType, sequenceData) {
    const color = this.colors[eventType] || this.colors.generic;
    const title = this.getTitle(props, eventType);
    const summary = sequenceData
      ? `${sequenceData.total_count || 0} events in this earthquake sequence`
      : 'Loading earthquake sequence...';

    return `
      <div class="disaster-popup popup-related" data-type="${eventType}" data-id="${props.event_id || ''}">
        <div class="popup-header-detail" style="border-left: 4px solid ${color}">
          <button class="popup-back" data-action="back">&lt; Back</button>
          <span class="popup-title-detail">Earthquake Sequence</span>
        </div>

        <div class="related-primary">
          <span class="related-icon" style="background: ${color}">${this.icons[eventType] || this.icons.generic}</span>
          <div class="related-info">
            <div class="related-title">${title}</div>
            <div class="related-subtitle">${this.getSubtitle(props, eventType)}</div>
          </div>
        </div>

        <div class="sequence-summary">
          <div class="seq-count">${summary}</div>
        </div>
      </div>
    `;
  },

  buildEarthquakeSequencePopup(props, eventType, sequenceData) {
    const color = this.colors[eventType] || this.colors.generic;
    const mainshock = sequenceData?.mainshock || props || {};
    const mainshockTitle = this.getTitle(mainshock, eventType);
    const totalCount = Number(sequenceData?.total_count) || 0;
    const visibleCount = Number(sequenceData?.visible_count) || 0;
    const rows = Array.isArray(sequenceData?.events) ? sequenceData.events : [];
    const summaryBits = [];
    if (mainshock?.magnitude != null) {
      summaryBits.push(`M ${Number(mainshock.magnitude).toFixed(1)}`);
    }
    if (mainshock?.timestamp) {
      summaryBits.push(this.formatDate(mainshock.timestamp));
    }
    const normalizedSummaryText = summaryBits.join(' - ');
    const summaryText = summaryBits.join(' · ');

    const listHtml = rows.length
      ? rows.map((evt, idx) => {
          const eventId = String(evt.event_id || '').trim();
          const mag = evt.magnitude != null ? `M ${Number(evt.magnitude).toFixed(1)}` : 'M ?';
          const timeText = evt.timestamp ? this.formatDate(evt.timestamp) : '';
          const role = idx === 0 || evt.is_mainshock ? 'Mainshock' : `Aftershock ${idx}`;
          const accent = this.getEarthquakeSequenceColor(evt.magnitude);
          const normalizedSublabel = [role, mag, timeText].filter(Boolean).join(' - ');
          const sublabel = [role, mag, timeText].filter(Boolean).join(' · ');
          return `<div class="sequence-item history-item" data-sequence-index="${idx}" style="border-left:3px solid ${accent}">
            <span class="seq-marker" style="color:${accent}">${idx === 0 || evt.is_mainshock ? 'M' : 'A'}</span>
            <span class="seq-label">${eventId || `Event ${idx + 1}`}</span>
            <span class="seq-sublabel" style="color:${accent}">${normalizedSublabel}</span>
          </div>`;
        }).join('\n')
      : '<div class="related-empty">No sequence events found.</div>';

    const overflowNote = totalCount > visibleCount
      ? `<div class="sequence-more">Showing ${visibleCount.toLocaleString()} of ${totalCount.toLocaleString()} events.</div>`
      : '';

    return `
      <div class="disaster-popup popup-sequence" data-type="${eventType}" data-id="${props.event_id || ''}">
        <div class="popup-header-detail" style="border-left: 4px solid ${color}">
          <button class="popup-back" data-action="back">&lt; Back</button>
          <span class="popup-title-detail">Earthquake Sequence</span>
        </div>

        <div class="sequence-summary">
          <strong>${mainshockTitle}</strong>
          <div class="seq-count">${totalCount.toLocaleString()} events in this sequence</div>
          ${normalizedSummaryText ? `<div class="sequence-meta">${normalizedSummaryText}</div>` : ''}
        </div>

        <div class="sequence-list">
          ${listHtml}
          ${overflowNote}
        </div>

        <div class="popup-actions">
          <button class="popup-btn btn-sequence" data-action="load-sequence">
            Animate Aftershocks
          </button>
          <button class="popup-btn btn-related" data-action="related">
            Related
          </button>
        </div>
      </div>
    `;
  },

  /**
   * Build unified hover HTML for all disaster types.
   * Styled to match the click popups with color-coding.
   * Shows: Name, Date, Intensity, "Click for details"
   * @param {Object} props - Feature properties
   * @param {string} eventType - Event type
   * @returns {string} HTML string
   */
  buildHoverHtml(props, eventType) {
    const icon = this.icons[eventType] || this.icons.generic;
    const color = this.colors[eventType] || this.colors.generic;
    const title = this.getTitle(props, eventType);

    // Get date - prefer date ranges, fallback to single date/year
    let dateStr = '';
    if (props.start_date && props.end_date) {
      dateStr = this.formatDateRange(props.start_date, props.end_date) || '';
    } else if (props.timestamp && props.end_timestamp) {
      dateStr = this.formatDateRange(props.timestamp, props.end_timestamp) || '';
    } else if (props.timestamp) {
      dateStr = this.formatDate(props.timestamp) || '';
    } else if (props.year) {
      dateStr = props.year < 0 ? `${Math.abs(props.year)} BCE` : props.year.toString();
    }

    // Get intensity/power value
    const power = this.formatPower(props, eventType);
    const intensityStr = power.value !== 'N/A' ? power.value : '';

    // Build compact hover HTML with styling
    return `
      <div class="disaster-hover" style="border-left: 3px solid ${color}">
        <div class="hover-header">
          <span class="hover-icon" style="background: ${color}">${icon}</span>
          <span class="hover-title">${title}</span>
        </div>
        ${dateStr ? `<div class="hover-date">${dateStr}</div>` : ''}
        ${intensityStr ? `<div class="hover-intensity">${intensityStr}${power.detail ? ` <span class="hover-detail">${power.detail}</span>` : ''}</div>` : ''}
        <div class="hover-hint">Click for details</div>
      </div>
    `;
  },

  async hydrateBasicPopupCounts(props, eventType) {
    if (eventType !== 'earthquake') {
      return;
    }

    const eventId = String(props?.event_id || '').trim();
    const mainshockId = String(props?.mainshock_id || '').trim();
    const countSourceEventId = mainshockId || eventId;
    if (!eventId) {
      return;
    }

    const cacheKey = `basic_${eventType}_${countSourceEventId}`;
    if (this.basicCountCache[cacheKey]) {
      const cached = this.basicCountCache[cacheKey];
      Object.assign(props, cached);
      if (this.currentEvent && String(this.currentEvent?.event_id || '').trim() === eventId) {
          Object.assign(this.currentEvent, cached);
      }
      return;
    }

    if (Number(props?.aftershock_count) > 0) {
      this.basicCountCache[cacheKey] = { aftershock_count: Number(props.aftershock_count) };
      return;
    }

    try {
      const data = await fetchMsgpack(`/api/earthquakes/aftershocks/${encodeURIComponent(countSourceEventId)}`);
      const aftershockCount = Number(data?.metadata?.aftershock_count);
      if (!Number.isFinite(aftershockCount) || aftershockCount <= 0) {
        return;
      }

      const hydrated = {
        aftershock_count: aftershockCount,
        mainshock_id: countSourceEventId !== eventId ? countSourceEventId : (props?.mainshock_id || null)
      };
      this.basicCountCache[cacheKey] = hydrated;
      Object.assign(props, hydrated);
      if (this.currentEvent && String(this.currentEvent?.event_id || '').trim() === eventId) {
        Object.assign(this.currentEvent, hydrated);
      }

      if (
        this.state === 'BASIC'
        && this.currentType === eventType
        && String(this.currentEvent?.event_id || '').trim() === eventId
      ) {
        const html = this.buildBasicPopup(this.currentEvent, this.currentType);
        this.updatePopupContent(html);
      }
    } catch (error) {
      console.warn('Could not hydrate popup earthquake counts:', error);
    }
  },

  /**
   * Show basic popup
   */
  show(lngLat, props, eventType) {
    this.currentEvent = props;
    this.currentType = eventType;
    this.state = 'BASIC';

    const html = this.buildBasicPopup(props, eventType);

    if (MapAdapter) {
      MapAdapter.registerFeaturePopupClick?.();
      MapAdapter.showPopup(lngLat, html);
      MapAdapter.popupLocked = true;
      MapAdapter.setSelectedPopupContext?.({
        kind: 'event',
        eventType,
        properties: props
      });
    }

    // Setup button handlers after popup is in DOM
    setTimeout(() => this.setupButtonHandlers(), 50);
    void this.hydrateBasicPopupCounts(this.currentEvent, this.currentType);
  },

  /**
   * Setup click handlers for popup buttons
   */
  setupButtonHandlers() {
    const popup = document.querySelector('.disaster-popup');
    if (!popup) return;

    // Action buttons
    popup.querySelectorAll('.popup-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const action = btn.dataset.action;
        this.handleAction(action);
      });
    });

    // Back button
    popup.querySelectorAll('.popup-back').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.handleBack();
      });
    });

    // Tab buttons
    popup.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const tab = btn.dataset.tab;
        this.switchTab(tab);
      });
    });

    // Related items
    popup.querySelectorAll('.related-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const id = item.dataset.id;
        const type = item.dataset.type;
        const locId = item.dataset.locId || '';
        this.handleRelatedClick(id, type, locId);
      });
    });

    // Sequence items
    popup.querySelectorAll('.sequence-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (item.dataset.sequenceIndex != null && item.dataset.sequenceIndex !== '') {
          const index = Number(item.dataset.sequenceIndex);
          this.handleSequenceEntryClick(index);
          return;
        }
        if (item.classList.contains('history-item')) {
          const index = Number(item.dataset.historyIndex);
          this.handleHistoryItemClick(index);
          return;
        }
        const id = item.dataset.id;
        this.handleSequenceItemClick(id);
      });
    });
  },

  /**
   * Handle action button click
   */
  handleAction(action) {
    if (!this.currentEvent || !this.currentType) return;

    switch (action) {
      case 'details':
        this.showDetails();
        break;
      case 'sequence':
        this.showSequence();
        break;
      case 'load-sequence':
        this.loadSequence();
        break;
      case 'related':
        this.showRelated();
        break;
      case 'history':
        this.loadHistory();
        break;
      case 'view-chain':
        this.loadRelatedChain();
        break;
      case 'load-related':
        this.loadRelated();
        break;
    }
  },

  /**
   * Handle back button
   */
  handleBack() {
    const sequenceKey = String(this.currentEvent?.sequence_context_key || '').trim();
    if (this.state === 'DETAIL' && sequenceKey && this.cachedData[sequenceKey]) {
      this.state = 'SEQUENCE';
      const sequenceData = this.cachedData[sequenceKey];
      const anchorProps = sequenceData.anchor_event || this.currentEvent;
      const html = this.buildEarthquakeSequencePopup(anchorProps, this.currentType, sequenceData);
      this.updatePopupContent(html);
      return;
    }
    const historyKey = String(this.currentEvent?.history_context_key || '').trim();
    if (this.state === 'DETAIL' && historyKey && this.cachedData[historyKey]) {
      this.state = 'HISTORY';
      const historyData = this.cachedData[historyKey];
      const anchorProps = historyData.anchor_event || this.currentEvent;
      const html = this.buildHistoryPopup(anchorProps, this.currentType, historyData);
      this.updatePopupContent(html);
      return;
    }
    this.state = 'BASIC';
    const html = this.buildBasicPopup(this.currentEvent, this.currentType);
    this.updatePopupContent(html);
  },

  /**
   * Switch tab in detail view
   */
  switchTab(tabName) {
    const popup = document.querySelector('.disaster-popup');
    if (!popup) return;

    // Update tab buttons
    popup.querySelectorAll('.tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    // Update tab content
    popup.querySelectorAll('.tab-content').forEach(content => {
      content.classList.toggle('active', content.dataset.tab === tabName);
    });
  },

  /**
   * Show detail view
   */
  showDetails() {
    this.state = 'DETAIL';

    // For now, use local data. In future, fetch from API
    const html = this.buildDetailPopup(this.currentEvent, this.currentType, {});
    this.updatePopupContent(html);
  },

  /**
   * Show sequence view - triggers animations for all disaster types
   * All sequence actions (aftershocks, runups, tracks, progressions, extents)
   * are handled as map animations, not popup lists
   */
  showSequence() {
    if (this.currentType === 'earthquake') {
      this.state = 'SEQUENCE_CONFIRM';
      const cacheKey = String(this.currentEvent?.sequence_context_key || '').trim()
        || `eqseq_${this.currentType}_${this.currentEvent.event_id || 'focus'}`;
      if (this.cachedData[cacheKey]) {
        this.state = 'SEQUENCE';
        const html = this.buildEarthquakeSequencePopup(
          this.cachedData[cacheKey].anchor_event || this.currentEvent,
          this.currentType,
          this.cachedData[cacheKey]
        );
        this.updatePopupContent(html);
        return;
      }
      const html = this.buildEarthquakeSequenceConfirmPopup(this.currentEvent, this.currentType, null);
      this.updatePopupContent(html);
      this.triggerSequenceDataHandler();
      return;
    }
    this.state = 'SEQUENCE_CONFIRM';
    const html = this.buildSequenceConfirmPopup(this.currentEvent, this.currentType);
    this.updatePopupContent(html);
  },

  loadSequence() {
    this.triggerSequenceHandler();
    this.hide();
  },

  loadHistory() {
    this.state = 'HISTORY_CONFIRM';
    const cacheKey = String(this.currentEvent?.history_context_key || '').trim()
      || `hist_${this.currentType}_${this.currentEvent.event_id || this.currentEvent.volcano_name || 'focus'}`;
    if (this.cachedData[cacheKey]) {
      const historyData = this.cachedData[cacheKey];
      const anchorProps = historyData.anchor_event || this.currentEvent;
      const html = this.buildHistoryPopup(anchorProps, this.currentType, historyData);
      this.updatePopupContent(html);
      return;
    }
    const html = this.buildHistoryConfirmPopup(this.currentEvent, this.currentType, null);
    this.updatePopupContent(html);
    this.triggerHistoryHandler();
  },

  /**
   * Show related view
   */
  showRelated() {
    this.state = 'RELATED_CONFIRM';

    // Check cache first
    const cacheKey = `rel_${this.currentType}_${this.currentEvent.event_id}`;

    if (this.cachedData[cacheKey]) {
      const html = this.buildRelatedConfirmPopup(this.currentEvent, this.currentType, this.cachedData[cacheKey]);
      this.updatePopupContent(html);
      return;
    }

    // Show loading state
    const html = this.buildRelatedConfirmPopup(this.currentEvent, this.currentType, null);
    this.updatePopupContent(html);

    // Trigger existing related handlers
    this.triggerRelatedHandler();
  },

  loadRelated() {
    this.state = 'RELATED';
    const cacheKey = `rel_${this.currentType}_${this.currentEvent.event_id}`;
    const html = this.buildRelatedPopup(this.currentEvent, this.currentType, this.cachedData[cacheKey] || { related: [] });
    this.updatePopupContent(html);
  },

  loadRelatedChain() {
    this.triggerRelatedChainHandler();
    this.hide();
  },

  /**
   * Update popup content without closing
   */
  updatePopupContent(html) {
    const popupContent = document.querySelector('.maplibregl-popup-content');
    if (popupContent) {
      popupContent.innerHTML = html;
      setTimeout(() => this.setupButtonHandlers(), 50);
    }
  },

  /**
   * Trigger existing sequence handler based on event type
   */
  triggerSequenceHandler() {
    const props = this.currentEvent;
    const eventType = this.currentType;

    // Dispatch custom event that existing handlers can listen to
    document.dispatchEvent(new CustomEvent('disaster-sequence-request', {
      detail: {
        eventId: props.event_id,
        eventType: eventType,
        props: props
      }
    }));
  },

  triggerSequenceDataHandler() {
    const props = this.currentEvent;
    const eventType = this.currentType;

    document.dispatchEvent(new CustomEvent('disaster-sequence-data-request', {
      detail: {
        eventId: props.event_id,
        eventType,
        props
      }
    }));
  },

  /**
   * Trigger existing related handler based on event type
   */
  triggerRelatedHandler() {
    const props = this.currentEvent;
    const eventType = this.currentType;

    // Dispatch custom event that existing handlers can listen to
    document.dispatchEvent(new CustomEvent('disaster-related-request', {
      detail: {
        eventId: props.event_id,
        eventType: eventType,
        props: props
      }
    }));
  },

  triggerHistoryHandler() {
    const props = this.currentEvent;
    const eventType = this.currentType;

    document.dispatchEvent(new CustomEvent('disaster-history-request', {
      detail: {
        eventId: props.event_id,
        eventType,
        props
      }
    }));
  },

  triggerRelatedChainHandler() {
    const props = this.currentEvent;
    const eventType = this.currentType;

    document.dispatchEvent(new CustomEvent('disaster-related-chain-request', {
      detail: {
        eventId: props.event_id,
        eventType: eventType,
        props: props
      }
    }));
  },

  /**
   * Handle click on related item
   */
  handleRelatedClick(eventId, eventType, locId = '') {
    // Dispatch event for handling
    document.dispatchEvent(new CustomEvent('disaster-related-click', {
      detail: {
        eventId: eventId,
        eventType: eventType,
        locId: locId
      }
    }));
  },

  /**
   * Handle click on sequence item
   */
  handleSequenceItemClick(eventId) {
    // Dispatch event for handling
    document.dispatchEvent(new CustomEvent('disaster-sequence-item-click', {
      detail: {
        eventId: eventId,
        parentType: this.currentType,
        parentId: this.currentEvent?.event_id
      }
    }));
  },

  handleSequenceEntryClick(index) {
    const cacheKey = String(this.currentEvent?.sequence_context_key || '').trim()
      || `eqseq_${this.currentType}_${this.currentEvent.event_id || 'focus'}`;
    const sequenceData = this.cachedData[cacheKey] || null;
    const events = sequenceData?.events || [];
    const selected = events[index];
    if (!selected) return;
    this.currentEvent = {
      ...selected,
      sequence_context_key: cacheKey
    };
    this.state = 'DETAIL';
    const html = this.buildDetailPopup(this.currentEvent, this.currentType, {});
    this.updatePopupContent(html);
  },

  handleHistoryItemClick(index) {
    const cacheKey = String(this.currentEvent?.history_context_key || '').trim()
      || `hist_${this.currentType}_${this.currentEvent.event_id || this.currentEvent.volcano_name || 'focus'}`;
    const historyData = this.cachedData[cacheKey] || null;
    const events = historyData?.events || [];
    const selected = events[index];
    if (!selected) return;
    this.currentEvent = {
      ...selected,
      history_context_key: cacheKey
    };
    this.currentType = 'volcano';
    this.state = 'DETAIL';
    const html = this.buildDetailPopup(this.currentEvent, this.currentType, {});
    this.updatePopupContent(html);
  },

  /**
   * Hide popup
   */
  hide() {
    this.state = 'CLOSED';
    this.currentEvent = null;
    this.currentType = null;

    if (MapAdapter) {
      MapAdapter.hidePopup();
    }
  },

  /**
   * Check if popup is open
   */
  isOpen() {
    return this.state !== 'CLOSED';
  },

  /**
   * Get current state
   */
  getState() {
    return this.state;
  }
};

// Dependency injection
let MapAdapter = null;

export function setDependencies(deps) {
  if (deps.MapAdapter) MapAdapter = deps.MapAdapter;
}

// ES6 module export
export { DisasterPopup };

// Also expose globally for backwards compatibility
window.DisasterPopup = DisasterPopup;
