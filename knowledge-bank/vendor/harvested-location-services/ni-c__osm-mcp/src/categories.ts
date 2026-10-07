import { parseTagSelector, type TagSelector } from './backends/overpass.js';

/**
 * Curated shortcuts for the most common travel-planning POI categories. Any
 * other OSM tag can be passed directly as `key` or `key=value`.
 */
export const CATEGORIES: Record<string, string> = {
  restaurant: 'amenity=restaurant',
  cafe: 'amenity=cafe',
  bar: 'amenity=bar',
  pub: 'amenity=pub',
  fast_food: 'amenity=fast_food',
  ice_cream: 'amenity=ice_cream',
  hotel: 'tourism=hotel',
  hostel: 'tourism=hostel',
  guest_house: 'tourism=guest_house',
  apartment: 'tourism=apartment',
  camp_site: 'tourism=camp_site',
  attraction: 'tourism=attraction',
  museum: 'tourism=museum',
  gallery: 'tourism=gallery',
  viewpoint: 'tourism=viewpoint',
  information: 'tourism=information',
  artwork: 'tourism=artwork',
  castle: 'historic=castle',
  monument: 'historic=monument',
  ruins: 'historic=ruins',
  supermarket: 'shop=supermarket',
  bakery: 'shop=bakery',
  convenience: 'shop=convenience',
  pharmacy: 'amenity=pharmacy',
  hospital: 'amenity=hospital',
  doctors: 'amenity=doctors',
  police: 'amenity=police',
  atm: 'amenity=atm',
  bank: 'amenity=bank',
  fuel: 'amenity=fuel',
  charging_station: 'amenity=charging_station',
  parking: 'amenity=parking',
  toilets: 'amenity=toilets',
  drinking_water: 'amenity=drinking_water',
  bus_stop: 'highway=bus_stop',
  train_station: 'railway=station',
  tram_stop: 'railway=tram_stop',
  ferry_terminal: 'amenity=ferry_terminal',
  bicycle_rental: 'amenity=bicycle_rental',
  car_rental: 'amenity=car_rental',
  playground: 'leisure=playground',
  park: 'leisure=park',
  beach: 'natural=beach',
  swimming_pool: 'leisure=swimming_pool',
};

/** Resolves a category shortcut or a raw `key`/`key=value` filter. */
export function resolveCategory(input: string): TagSelector {
  // Object.hasOwn: a plain index lookup would walk the prototype chain, so
  // inputs like "constructor" would return a function instead of a string.
  const shortcut = Object.hasOwn(CATEGORIES, input)
    ? CATEGORIES[input]!
    : input;
  return parseTagSelector(shortcut);
}

export function categoryList(): string {
  return Object.keys(CATEGORIES).join(', ');
}
