import { z } from 'zod';
import { apiClient } from '../lib/api-client.js';
import type { Country } from '../lib/types.js';

export const compareCountriesSchema = {
  country_a: z.string().min(1).max(100).describe('First country name or slug (e.g. "brazil", "Japan")'),
  country_b: z.string().min(1).max(100).describe('Second country name or slug (e.g. "argentina", "South Korea")'),
};

export async function compareCountries({
  country_a,
  country_b,
}: {
  country_a: string;
  country_b: string;
}): Promise<string> {
  const slugA = country_a.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
  const slugB = country_b.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');

  const [responseA, responseB] = await Promise.all([
    apiClient.get<Country>(`/countries/${encodeURIComponent(slugA)}`),
    apiClient.get<Country>(`/countries/${encodeURIComponent(slugB)}`),
  ]);

  const a = responseA.data;
  const b = responseB.data;
  const nameA = a.names.en;
  const nameB = b.names.en;

  const lines: string[] = [
    `# ${nameA} vs ${nameB}`,
    '',
    '## Basic Information',
    '',
    `| Metric | ${nameA} | ${nameB} |`,
    '|--------|---------|---------|',
    `| ISO Code | ${a.iso_code || 'N/A'} | ${b.iso_code || 'N/A'} |`,
    `| Region | ${a.region?.name || 'N/A'} | ${b.region?.name || 'N/A'} |`,
    `| Category | ${a.category || 'N/A'} | ${b.category || 'N/A'} |`,
  ];

  // Stats comparison
  if (a.stats && b.stats) {
    lines.push('', '## Statistics Comparison', '');
    lines.push(`| Statistic | ${nameA} | ${nameB} |`);
    lines.push('|-----------|---------|---------|');

    // Merge all stat keys from both countries
    const allKeys = new Set([...Object.keys(a.stats), ...Object.keys(b.stats)]);

    for (const key of allKeys) {
      const statA = a.stats[key];
      const statB = b.stats[key];
      const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

      const formatVal = (stat: typeof statA) => {
        if (!stat || stat.value === null) return 'N/A';
        const unit = stat.unit ? ` ${stat.unit}` : '';
        return `${stat.value.toLocaleString('en-US')}${unit}`;
      };

      lines.push(`| ${label} | ${formatVal(statA)} | ${formatVal(statB)} |`);
    }
  }

  // Population density comparison
  const popA = a.stats?.population?.value;
  const popB = b.stats?.population?.value;
  const areaA = a.stats?.area_sq_km?.value;
  const areaB = b.stats?.area_sq_km?.value;

  if (popA && areaA && popB && areaB) {
    const densA = (popA / areaA).toFixed(1);
    const densB = (popB / areaB).toFixed(1);
    lines.push('', `**Population density:** ${nameA}: ${densA}/km² | ${nameB}: ${densB}/km²`);
  }

  return lines.join('\n');
}
