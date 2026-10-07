import { z } from 'zod';
import { apiClient } from '../lib/api-client.js';
import type { City } from '../lib/types.js';

export const getCitySchema = {
  city_id: z.number().int().positive().describe('The GeoNames ID of the city (e.g. 1850147 for Tokyo, 3435910 for Buenos Aires)'),
};

export async function getCity({ city_id }: { city_id: number }): Promise<string> {
  const response = await apiClient.get<City>(`/cities/${city_id}`);
  const c = response.data;

  const name = c.names?.en || 'Unknown';
  const lines: string[] = [`# ${name}`, ''];

  if (c.population) lines.push(`**Population:** ${c.population.toLocaleString('en-US')}`);
  if (c.coordinates) lines.push(`**Coordinates:** ${c.coordinates.latitude}°N, ${c.coordinates.longitude}°E`);
  if (c.elevation != null) lines.push(`**Elevation:** ${c.elevation}m`);
  if (c.timezone) lines.push(`**Timezone:** ${c.timezone}`);
  if (c.province) lines.push(`**Province:** ${c.province}`);
  if (c.feature_code) lines.push(`**Feature:** ${c.feature_code}`);

  // Other language names
  const otherLangs = [];
  if (c.names.es && c.names.es !== name) otherLangs.push(`ES: ${c.names.es}`);
  if (c.names.pt && c.names.pt !== name) otherLangs.push(`PT: ${c.names.pt}`);
  if (c.names.it && c.names.it !== name) otherLangs.push(`IT: ${c.names.it}`);
  if (otherLangs.length > 0) {
    lines.push('', `**Other names:** ${otherLangs.join(' | ')}`);
  }

  return lines.join('\n');
}
