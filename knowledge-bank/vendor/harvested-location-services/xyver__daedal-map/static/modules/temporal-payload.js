const TIMESTAMP_GRANULARITIES = new Set([
  'timestamp',
  'seconds',
  '12m',
  '1h',
  '2h',
  '6h',
  '12h',
  'daily',
  '2d',
  'weekly',
  'monthly'
]);

function isNumericYearValue(value) {
  if (typeof value === 'number') {
    return Number.isFinite(value) && Math.abs(value) < 100000;
  }
  if (typeof value !== 'string') return false;
  const trimmed = value.trim();
  if (!trimmed) return false;
  if (!/^-?\d+$/.test(trimmed)) return false;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) && Math.abs(parsed) < 100000;
}

function isEpochLikeTimestamp(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && Math.abs(parsed) >= 1000000000;
}

function coerceAvailableTimes(rawRange, timeData) {
  if (Array.isArray(rawRange?.available)) {
    return rawRange.available;
  }
  if (Array.isArray(rawRange?.available_years)) {
    return rawRange.available_years;
  }
  if (Array.isArray(rawRange)) {
    return rawRange;
  }
  return Object.keys(timeData || {});
}

function coerceMinMax(rawRange, availableTimes) {
  if (rawRange && !Array.isArray(rawRange)) {
    if (rawRange.min != null || rawRange.max != null) {
      return {
        min: rawRange.min,
        max: rawRange.max
      };
    }
  }

  if (Array.isArray(rawRange) && rawRange.length >= 2) {
    return {
      min: rawRange[0],
      max: rawRange[rawRange.length - 1]
    };
  }

  if (availableTimes.length) {
    const sorted = [...availableTimes].sort((a, b) => Number(a) - Number(b));
    return {
      min: sorted[0],
      max: sorted[sorted.length - 1]
    };
  }

  return { min: null, max: null };
}

function inferGranularity(rawRange, availableTimes, data) {
  const explicit =
    rawRange?.granularity ||
    data?.time_granularity ||
    data?.granularity ||
    null;
  if (explicit) return explicit;

  if (availableTimes.some(isEpochLikeTimestamp)) {
    return 'daily';
  }
  if (availableTimes.every(isNumericYearValue)) {
    return 'yearly';
  }
  return 'yearly';
}

function sortTemporalValues(values) {
  return [...new Set(values)].sort((a, b) => Number(a) - Number(b));
}

export function getTemporalMetricPayload(data) {
  const timeData = data?.time_data || data?.year_data || null;
  const rawRange = data?.time_range || data?.year_range || null;
  if (!timeData || !rawRange) return null;

  const available = coerceAvailableTimes(rawRange, timeData);
  const { min, max } = coerceMinMax(rawRange, available);
  const granularity = inferGranularity(rawRange, available, data);
  const useTimestamps =
    Boolean(rawRange?.useTimestamps) ||
    TIMESTAMP_GRANULARITIES.has(granularity) ||
    available.some(isEpochLikeTimestamp);

  return {
    timeData,
    timeRange: {
      min,
      max,
      available,
      granularity,
      useTimestamps
    },
    metricTimeRanges: data?.metric_time_ranges || data?.metric_year_ranges || {},
    availableMetrics: data?.available_metrics || [],
    metricKey: data?.metric_key || null
  };
}

export function hasTemporalMetricPayload(data) {
  return Boolean(getTemporalMetricPayload(data));
}

export function mergeTemporalMetricPayload(existing, incoming) {
  const existingTemporal = getTemporalMetricPayload(existing);
  const incomingTemporal = getTemporalMetricPayload(incoming);
  if (!existingTemporal || !incomingTemporal) {
    return incomingTemporal || existingTemporal || null;
  }

  const mergedTimeData = { ...(existingTemporal.timeData || {}) };
  for (const [timeKey, locData] of Object.entries(incomingTemporal.timeData || {})) {
    if (!mergedTimeData[timeKey]) {
      mergedTimeData[timeKey] = {};
    }
    for (const [locId, metrics] of Object.entries(locData || {})) {
      if (!mergedTimeData[timeKey][locId]) {
        mergedTimeData[timeKey][locId] = {};
      }
      Object.assign(mergedTimeData[timeKey][locId], metrics || {});
    }
  }

  const mergedAvailable = sortTemporalValues([
    ...(existingTemporal.timeRange?.available || []),
    ...(incomingTemporal.timeRange?.available || [])
  ]);

  const mergedMin = existingTemporal.timeRange?.min != null && incomingTemporal.timeRange?.min != null
    ? Math.min(existingTemporal.timeRange.min, incomingTemporal.timeRange.min)
    : (existingTemporal.timeRange?.min ?? incomingTemporal.timeRange?.min ?? null);
  const mergedMax = existingTemporal.timeRange?.max != null && incomingTemporal.timeRange?.max != null
    ? Math.max(existingTemporal.timeRange.max, incomingTemporal.timeRange.max)
    : (existingTemporal.timeRange?.max ?? incomingTemporal.timeRange?.max ?? null);

  return {
    timeData: mergedTimeData,
    timeRange: {
      min: mergedMin,
      max: mergedMax,
      available: mergedAvailable,
      granularity: incomingTemporal.timeRange?.granularity || existingTemporal.timeRange?.granularity || 'yearly',
      useTimestamps: Boolean(
        incomingTemporal.timeRange?.useTimestamps ||
        existingTemporal.timeRange?.useTimestamps
      )
    },
    metricTimeRanges: {
      ...(existingTemporal.metricTimeRanges || {}),
      ...(incomingTemporal.metricTimeRanges || {})
    },
    availableMetrics: [...new Set([
      ...(existingTemporal.availableMetrics || []),
      ...(incomingTemporal.availableMetrics || [])
    ])],
    metricKey: incomingTemporal.metricKey || existingTemporal.metricKey || null
  };
}
