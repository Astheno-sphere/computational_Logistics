import type { TFunction } from 'i18next';
import type { VscodeThemePalette } from '../theme';
import {
  isUsageApp,
  selectAccountingUsageRecords,
  sanitizeUsageRecords,
} from '../../services/gatewayUsageTracker';
import { formatCost } from './modelPricing';
import type { TokenUsageRecord, UsageAggregation, UsageModelStats, UsageProviderStats } from './gatewayUsageTypes';

export type UsageAppFilter = 'all' | 'claude' | 'codex';
export type UsageRangeFilter = 'today' | '7d' | '30d' | 'all';
export type UsageTrendMetric = 'requests' | 'tokens' | 'cost';

export type UsageChartSeries = {
  id: string;
  label: string;
  color: string;
  values: number[];
};

export function formatTokenCount(n: number): string {
  if (n >= 1_000_000_000) {
    return `${(n / 1_000_000_000).toFixed(1)}B`;
  }
  if (n >= 1_000_000) {
    return `${(n / 1_000_000).toFixed(1)}M`;
  }
  if (n >= 1_000) {
    return `${(n / 1_000).toFixed(1)}K`;
  }
  return String(Math.round(n));
}

export function formatChartCost(cost: number): string {
  if (cost <= 0) {
    return '$0';
  }
  if (cost < 0.01) {
    return `$${cost.toFixed(4)}`;
  }
  return formatCost(cost);
}

export function localDateKey(value: string | number | Date): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function emptyStats(): UsageModelStats {
  return { input: 0, output: 0, cacheRead: 0, cacheCreation: 0, requests: 0 };
}

export function addToStats(stats: UsageModelStats, record: TokenUsageRecord): void {
  stats.input += record.inputTokens;
  stats.output += record.outputTokens;
  stats.cacheRead += record.cacheReadTokens;
  stats.cacheCreation += record.cacheCreationTokens;
  stats.requests += 1;
}

/** Explicit app only; records without app must be dropped via sanitizeUsageRecords first. */
export function recordApp(record: TokenUsageRecord): 'claude' | 'codex' {
  if (!isUsageApp(record.app)) {
    throw new Error('usage_record_missing_app');
  }
  return record.app;
}

export function isProbeUsageRecord(record: TokenUsageRecord): boolean {
  return record.model === 'models-list';
}

export function filterProbeRecords(records: TokenUsageRecord[]): TokenUsageRecord[] {
  return records.filter((record) => !isProbeUsageRecord(record));
}

export function selectAccountingRecords(
  records: TokenUsageRecord[]
): TokenUsageRecord[] {
  return selectAccountingUsageRecords(records);
}

export function hasChatUsageRecords(records: TokenUsageRecord[]): boolean {
  return records.some((record) => !isProbeUsageRecord(record));
}

export function filterRecordsByRange(
  records: TokenUsageRecord[],
  range: UsageRangeFilter
): TokenUsageRecord[] {
  if (range === 'all') {
    return records;
  }
  if (range === 'today') {
    const today = localDateKey(Date.now());
    return records.filter((record) => localDateKey(record.ts) === today);
  }
  const days = range === '7d' ? 7 : 30;
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  return records.filter((record) => {
    const ts = Date.parse(record.ts);
    return Number.isFinite(ts) && ts >= cutoff;
  });
}

export function filterRecordsByApp(
  records: TokenUsageRecord[],
  app: UsageAppFilter
): TokenUsageRecord[] {
  if (app === 'all') {
    return records;
  }
  return records.filter((record) => recordApp(record) === app);
}

export function aggregateGatewayUsage(records: TokenUsageRecord[]): UsageAggregation | null {
  const usable = sanitizeUsageRecords(records);
  if (usable.length === 0) {
    return null;
  }
  const aggregation: UsageAggregation = {
    totalInputTokens: 0,
    totalOutputTokens: 0,
    totalCacheReadTokens: 0,
    totalCacheCreationTokens: 0,
    totalRequests: usable.length,
    totalTokens: 0,
    cacheHitRate: 0,
    byModel: {},
    byDay: {},
    byApp: { claude: emptyStats(), codex: emptyStats() },
    timeSeries: [],
  };
  const bucketMap = new Map<string, UsageAggregation['timeSeries'][number]>();
  for (const record of usable) {
    aggregation.totalInputTokens += record.inputTokens;
    aggregation.totalOutputTokens += record.outputTokens;
    aggregation.totalCacheReadTokens += record.cacheReadTokens;
    aggregation.totalCacheCreationTokens += record.cacheCreationTokens;

    const model = record.model || 'unknown';
    const modelStats = aggregation.byModel[model] ?? emptyStats();
    addToStats(modelStats, record);
    aggregation.byModel[model] = modelStats;

    const day = localDateKey(record.ts);
    const dayStats = aggregation.byDay[day] ?? emptyStats();
    addToStats(dayStats, record);
    aggregation.byDay[day] = dayStats;

    addToStats(aggregation.byApp[recordApp(record)], record);

    const bucket = bucketMap.get(day) ?? {
      key: day,
      label: day.slice(5),
      requests: 0,
      inputTokens: 0,
      outputTokens: 0,
      cacheReadTokens: 0,
      cacheCreationTokens: 0,
    };
    bucket.requests += 1;
    bucket.inputTokens += record.inputTokens;
    bucket.outputTokens += record.outputTokens;
    bucket.cacheReadTokens += record.cacheReadTokens;
    bucket.cacheCreationTokens += record.cacheCreationTokens;
    bucketMap.set(day, bucket);
  }
  aggregation.totalTokens =
    aggregation.totalInputTokens +
    aggregation.totalOutputTokens +
    aggregation.totalCacheReadTokens +
    aggregation.totalCacheCreationTokens;
  const cacheable = aggregation.totalInputTokens + aggregation.totalCacheReadTokens;
  aggregation.cacheHitRate = cacheable > 0
    ? Math.min(100, (aggregation.totalCacheReadTokens / cacheable) * 100)
    : 0;
  aggregation.timeSeries = [...bucketMap.values()]
    .sort((a, b) => a.key.localeCompare(b.key))
    .slice(-30);
  return aggregation;
}

export function emptyAggregation(): UsageAggregation {
  return {
    totalInputTokens: 0,
    totalOutputTokens: 0,
    totalCacheReadTokens: 0,
    totalCacheCreationTokens: 0,
    totalRequests: 0,
    totalTokens: 0,
    cacheHitRate: 0,
    byModel: {},
    byDay: {},
    byApp: { claude: emptyStats(), codex: emptyStats() },
    timeSeries: [],
  };
}

export function resolveGatewayUsageView(
  records: TokenUsageRecord[],
  options?: { range?: UsageRangeFilter; app?: UsageAppFilter }
): UsageAggregation | null {
  const range = options?.range ?? 'all';
  const app = options?.app ?? 'all';
  const clean = sanitizeUsageRecords(records);
  const ranged = filterRecordsByRange(clean, range);
  const filtered = filterRecordsByApp(ranged, app);
  return aggregateGatewayUsage(filtered);
}

export function resolveRecordProvider(record: TokenUsageRecord): string {
  return record.provider?.trim() || record.upstream || 'unknown';
}

export function computeUsageSuccessRate(records: TokenUsageRecord[]): number | null {
  const withStatus = records.filter((record) => typeof record.status === 'number');
  if (withStatus.length === 0) {
    return null;
  }
  const successes = withStatus.filter((record) => {
    const status = record.status ?? 0;
    return status >= 200 && status < 300;
  }).length;
  return Math.round((successes / withStatus.length) * 1000) / 10;
}

export function aggregateByProvider(records: TokenUsageRecord[]): UsageProviderStats[] {
  const map = new Map<string, UsageProviderStats>();
  for (const record of records) {
    const provider = resolveRecordProvider(record);
    const stats = map.get(provider) ?? {
      provider,
      requests: 0,
      successes: 0,
      failures: 0,
      input: 0,
      output: 0,
      cacheRead: 0,
      cacheCreation: 0,
    };
    stats.requests += 1;
    const status = record.status;
    if (typeof status === 'number') {
      if (status >= 200 && status < 300) {
        stats.successes += 1;
      } else {
        stats.failures += 1;
      }
    }
    stats.input += record.inputTokens;
    stats.output += record.outputTokens;
    stats.cacheRead += record.cacheReadTokens;
    stats.cacheCreation += record.cacheCreationTokens;
    map.set(provider, stats);
  }
  return [...map.values()].sort((a, b) => b.requests - a.requests);
}

export function buildUsageChartSeries(
  aggregation: UsageAggregation,
  metric: UsageTrendMetric,
  t: TFunction,
  palette: VscodeThemePalette,
  costValues?: number[]
): { labels: string[]; series: UsageChartSeries[] } {
  const labels = aggregation.timeSeries.map((bucket) => bucket.label);
  if (metric === 'requests') {
    return {
      labels,
      series: [
        {
          id: 'requests',
          label: t('claudeCodeConfig.usageChartRequests'),
          color: palette.linkForeground,
          values: aggregation.timeSeries.map((bucket) => bucket.requests),
        },
      ],
    };
  }
  if (metric === 'cost' && costValues) {
    return {
      labels,
      series: [
        {
          id: 'cost',
          label: t('claudeCodeConfig.usageEstCost'),
          color: '#fa541c',
          values: costValues,
        },
      ],
    };
  }
  const tokenSeries: UsageChartSeries[] = [
    {
      id: 'input',
      label: t('claudeCodeConfig.usageColInput'),
      color: '#1677ff',
      values: aggregation.timeSeries.map((bucket) => bucket.inputTokens),
    },
    {
      id: 'output',
      label: t('claudeCodeConfig.usageColOutput'),
      color: '#52c41a',
      values: aggregation.timeSeries.map((bucket) => bucket.outputTokens),
    },
    {
      id: 'cacheRead',
      label: t('claudeCodeConfig.usageCacheRead'),
      color: '#722ed1',
      values: aggregation.timeSeries.map((bucket) => bucket.cacheReadTokens),
    },
    {
      id: 'cacheCreate',
      label: t('claudeCodeConfig.usageCacheCreation'),
      color: '#fa8c16',
      values: aggregation.timeSeries.map((bucket) => bucket.cacheCreationTokens),
    },
  ].filter((item) => item.values.some((value) => value > 0));
  return { labels, series: tokenSeries };
}

export function hasGatewayUsageData(aggregation: UsageAggregation | null): boolean {
  if (!aggregation) {
    return false;
  }
  return (
    aggregation.totalRequests > 0 ||
    aggregation.totalInputTokens > 0 ||
    aggregation.totalOutputTokens > 0 ||
    aggregation.totalCacheReadTokens > 0 ||
    aggregation.totalCacheCreationTokens > 0
  );
}
