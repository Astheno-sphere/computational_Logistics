import { z } from 'zod';
import { apiClient } from '../lib/api-client.js';
import type { SearchResult } from '../lib/types.js';

export const searchCitiesSchema = {
  query: z.string().min(2).max(200).describe('City name or partial name to search for (min 2 characters)'),
  limit: z.number().min(1).max(50).default(20).describe('Maximum results to return (1-50, default 20)'),
};

export async function searchCities({
  query,
  limit,
}: {
  query: string;
  limit: number;
}): Promise<string> {
  const response = await apiClient.get<SearchResult[]>('/search', {
    q: query,
    type: 'city',
    limit,
  });

  const results = response.data;

  if (!results || results.length === 0) {
    return `No cities found matching "${query}". Try a different search term or check the spelling.`;
  }

  const lines: string[] = [
    `## Cities matching "${query}"`,
    '',
  ];

  for (const r of results) {
    const name = r.names?.en || '?';
    const pop = r.population ? ` | Pop: ${r.population.toLocaleString('en-US')}` : '';
    const cc = r.country_code ? ` (${r.country_code})` : '';
    const prov = r.province ? ` — ${r.province}` : '';
    lines.push(`- **${name}**${cc}${prov}${pop}`);
  }

  return lines.join('\n');
}
