/**
 * Type definitions matching the actual Bamwor API response shapes.
 */

export interface MultiLangNames {
  en: string;
  es?: string;
  pt?: string;
  it?: string;
}

export interface Coordinates {
  latitude: number;
  longitude: number;
}

export interface CountryStat {
  value: number | null;
  unit?: string | null;
  year?: number | null;
  source?: string | null;
}

export interface Country {
  gec_code: string;
  iso_code?: string;
  names: MultiLangNames;
  slugs: MultiLangNames;
  coordinates?: Coordinates;
  region?: { slug: string; name: string };
  population?: number | null;
  area_sq_km?: number | null;
  category?: string;
  flag_url?: string | null;
  map_url?: string | null;
  stats?: Record<string, CountryStat>;
}

export interface City {
  id: number;
  names: MultiLangNames;
  slugs?: MultiLangNames;
  coordinates: Coordinates;
  population: number;
  elevation?: number | null;
  timezone?: string | null;
  feature_code?: string;
  province?: string | null;
  country_code?: string;
}

export interface SearchResult {
  type: 'country' | 'city';
  id: number;
  names: MultiLangNames;
  slugs?: MultiLangNames;
  coordinates?: Coordinates;
  population?: number;
  country_code?: string;
  province?: string;
  region?: { slug: string; name: string };
}
