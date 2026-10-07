import { z } from 'zod';
import { apiClient } from '../lib/api-client.js';
import type { City } from '../lib/types.js';

export const listCitiesByCountrySchema = {
  country: z.string().min(1).max(100).describe('Country name or slug (e.g. "brazil", "Japan", "united-states")'),
  min_population: z.number().min(0).max(2_000_000_000).optional().describe('Minimum population filter (e.g. 1000000 for cities above 1M)'),
  limit: z.number().min(1).max(50).default(25).describe('Maximum results to return (1-50, default 25)'),
  sort: z.enum(['population', 'name']).default('population').describe('Sort order: "population" (default, descending) or "name" (ascending)'),
};

export async function listCitiesByCountry({
  country,
  min_population,
  limit,
  sort,
}: {
  country: string;
  min_population?: number;
  limit: number;
  sort: string;
}): Promise<string> {
  const slug = country.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');

  const response = await apiClient.get<City[]>(`/countries/${encodeURIComponent(slug)}/cities`, {
    sort,
    min_population,
    per_page: limit,
  });

  const cities = response.data;

  if (!cities || cities.length === 0) {
    const minPopNote = min_population ? ` above ${min_population.toLocaleString('en-US')} population` : '';
    return `No cities found for country "${country}"${minPopNote}. Check the country name or try a lower population threshold.`;
  }

  const total = response.pagination?.total || cities.length;

  const lines: string[] = [
    `## Cities in ${country}`,
    '',
    `Showing ${cities.length} of ${total} cities${min_population ? ` (population >= ${min_population.toLocaleString('en-US')})` : ''}, sorted by ${sort}:`,
    '',
  ];

  for (let i = 0; i < cities.length; i++) {
    const c = cities[i];
    const name = c.names?.en || '?';
    const pop = c.population ? c.population.toLocaleString('en-US') : 'N/A';
    const region = c.province ? ` — ${c.province}` : '';
    lines.push(`${i + 1}. **${name}**${region} | Population: ${pop}`);
  }

  if (total > cities.length) {
    lines.push('', `_Showing ${cities.length} of ${total} total cities. Increase limit or use min_population to narrow results._`);
  }

  return lines.join('\n');
}
