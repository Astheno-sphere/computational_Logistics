import { z } from 'zod';
import { apiClient } from '../lib/api-client.js';

interface NearbyCity {
  id: number;
  names: { en: string; es?: string; pt?: string; it?: string };
  coordinates: { latitude: number; longitude: number };
  population: number;
  distance_km?: number;
  province?: string | null;
}

export const getNearbyCitiesSchema = {
  city_id: z.number().int().positive().describe('GeoNames ID of the reference city (e.g. 1850147 for Tokyo)'),
  radius: z.number().min(1).max(200).default(50).describe('Search radius in kilometers (1-200, default 50)'),
  limit: z.number().min(1).max(50).default(10).describe('Maximum results to return (1-50, default 10)'),
};

export async function getNearbyCities({
  city_id,
  radius,
  limit,
}: {
  city_id: number;
  radius: number;
  limit: number;
}): Promise<string> {
  const response = await apiClient.get<NearbyCity[]>(`/cities/${city_id}/nearby`, {
    radius,
    limit,
  });

  const cities = response.data;

  if (!cities || cities.length === 0) {
    return `No cities found within ${radius}km of city ID ${city_id}. Try increasing the radius.`;
  }

  const lines: string[] = [
    `## Cities within ${radius}km`,
    '',
    `Found ${cities.length} nearby cities:`,
    '',
    '| City | Distance | Population |',
    '|------|----------|------------|',
  ];

  for (const c of cities) {
    const name = c.names?.en || '?';
    const dist = c.distance_km != null ? `${c.distance_km.toFixed(1)} km` : 'N/A';
    const pop = c.population ? c.population.toLocaleString('en-US') : 'N/A';
    lines.push(`| ${name} | ${dist} | ${pop} |`);
  }

  return lines.join('\n');
}
