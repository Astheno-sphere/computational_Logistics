import { z } from 'zod';
import { apiClient } from '../lib/api-client.js';
import type { SearchResult } from '../lib/types.js';

export const searchCountriesSchema = {
  query: z.string().min(1).max(200).describe('Search term (country name, partial name, or keyword)'),
  limit: z.number().min(1).max(50).default(25).describe('Maximum results to return (1-50, default 25)'),
};

export async function searchCountries({
  query,
  limit,
}: {
  query: string;
  limit: number;
}): Promise<string> {
  const response = await apiClient.get<SearchResult[]>('/search', {
    q: query,
    type: 'country',
    limit,
  });

  const results = response.data;

  if (!results || results.length === 0) {
    return `No countries found matching "${query}". Try a different search term.`;
  }

  const lines: string[] = [
    `## Countries matching "${query}"`,
    '',
  ];

  for (const r of results) {
    const name = r.names?.en || '?';
    const pop = r.population ? ` | Pop: ${r.population.toLocaleString('en-US')}` : '';
    const reg = r.region ? ` | ${r.region.name}` : '';
    lines.push(`- **${name}**${reg}${pop}`);
  }

  return lines.join('\n');
}
