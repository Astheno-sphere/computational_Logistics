import { z } from 'zod';
import { apiClient } from '../lib/api-client.js';
import type { Country } from '../lib/types.js';

export const getCountrySchema = {
  query: z.string().min(1).max(100).describe(
    'Country name (e.g. "Brazil"), slug (e.g. "brazil"), or ISO code (e.g. "BR")'
  ),
};

export async function getCountry({ query }: { query: string }): Promise<string> {
  const sanitized = query.trim().slice(0, 100);
  const slug = sanitized.length <= 3
    ? sanitized.toLowerCase()
    : sanitized.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');

  try {
    const response = await apiClient.get<Country>(`/countries/${encodeURIComponent(slug)}`);
    const c = response.data;

    const name = c.names.en;
    const lines: string[] = [`# ${name}`, ''];

    if (c.region) lines.push(`**Region:** ${c.region.name}`);
    if (c.iso_code) lines.push(`**ISO Code:** ${c.iso_code}`);
    if (c.coordinates) lines.push(`**Coordinates:** ${c.coordinates.latitude}, ${c.coordinates.longitude}`);
    if (c.category) lines.push(`**Category:** ${c.category}`);

    // Stats
    if (c.stats && Object.keys(c.stats).length > 0) {
      lines.push('', '## Statistics', '');
      for (const [key, stat] of Object.entries(c.stats)) {
        if (stat.value !== null) {
          const unit = stat.unit ? ` ${stat.unit}` : '';
          const year = stat.year ? ` (${stat.year})` : '';
          const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
          lines.push(`- **${label}:** ${stat.value.toLocaleString('en-US')}${unit}${year}`);
        }
      }
    }

    // Also available in other languages
    const otherLangs = [];
    if (c.names.es && c.names.es !== name) otherLangs.push(`ES: ${c.names.es}`);
    if (c.names.pt && c.names.pt !== name) otherLangs.push(`PT: ${c.names.pt}`);
    if (c.names.it && c.names.it !== name) otherLangs.push(`IT: ${c.names.it}`);
    if (otherLangs.length > 0) {
      lines.push('', `**Other names:** ${otherLangs.join(' | ')}`);
    }

    return lines.join('\n');
  } catch (error) {
    if (String(error).includes('404') || String(error).includes('NOT_FOUND')) {
      return `Country "${query}" not found. Try using the full country name or ISO code. Use search_countries to find available countries.`;
    }
    throw error;
  }
}
