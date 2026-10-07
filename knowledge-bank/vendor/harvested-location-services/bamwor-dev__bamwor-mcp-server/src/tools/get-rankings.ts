import { z } from 'zod';
import { apiClient } from '../lib/api-client.js';

interface RankingMetric {
  slug: string;
  label: string;
  url: string;
}

interface RankingEntry {
  rank: number;
  country: {
    names: { en: string };
    iso_code?: string;
    region?: { name: string };
  };
  value: number;
  unit?: string | null;
  year?: number | null;
}

export const getRankingsSchema = {
  metric: z.string().max(30).optional().describe(
    'Ranking metric slug (e.g. "population", "gdp", "hdi", "ibeu"). Omit to list all available metrics.'
  ),
  limit: z.number().min(1).max(50).default(10).describe('Maximum results to return (1-50, default 10)'),
  countries_only: z.boolean().default(true).describe('Filter to sovereign countries only, excluding World/EU/territories (default true)'),
};

export async function getRankings({
  metric,
  limit,
  countries_only,
}: {
  metric?: string;
  limit: number;
  countries_only: boolean;
}): Promise<string> {
  // If no metric, return list of available metrics
  if (!metric) {
    const response = await apiClient.get<RankingMetric[]>('/rankings');
    const metrics = response.data;

    const lines: string[] = [
      '## Available Ranking Metrics',
      '',
      `${metrics.length} metrics available:`,
      '',
    ];

    for (const m of metrics) {
      lines.push(`- **${m.slug}** — ${m.label}`);
    }

    lines.push('', '_Use get_rankings with a metric slug to see the ranking._');
    return lines.join('\n');
  }

  // Fetch ranking data
  const response = await apiClient.get<RankingEntry[]>(`/rankings/${encodeURIComponent(metric)}`, {
    per_page: limit,
    countries_only: countries_only ? 'true' : undefined,
  });

  const entries = response.data;
  const total = response.pagination?.total || entries.length;

  if (!entries || entries.length === 0) {
    return `No data found for ranking "${metric}". Use get_rankings without a metric to see available options.`;
  }

  const lines: string[] = [
    `## Ranking: ${metric}`,
    '',
    `Showing top ${entries.length} of ${total}${countries_only ? ' countries' : ' entities'}:`,
    '',
    '| Rank | Country | Value |',
    '|------|---------|-------|',
  ];

  for (const entry of entries) {
    const name = entry.country.names.en;
    const unit = entry.unit ? ` ${entry.unit}` : '';
    const val = typeof entry.value === 'number' ? entry.value.toLocaleString('en-US') : String(entry.value);
    lines.push(`| ${entry.rank} | ${name} | ${val}${unit} |`);
  }

  if (total > entries.length) {
    lines.push('', `_Showing ${entries.length} of ${total} total. Increase limit to see more._`);
  }

  return lines.join('\n');
}
