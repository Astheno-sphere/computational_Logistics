/**
 * Google Places type → GeoWire 표준 카테고리 매핑.
 * nominatim과 **동일한 표준 카테고리 집합**으로 정규화해 dedup·필터가 공급자 간 일관되게 동작한다.
 * 커뮤니티 PR로 확장하는 데이터 파일이다(good-first-issue).
 */
export const GOOGLE_CATEGORY_MAP: Record<string, string> = {
  pharmacy: "pharmacy",
  drugstore: "pharmacy",
  hospital: "hospital",
  clinic: "clinic",
  doctor: "doctor",
  dentist: "dentist",
  restaurant: "restaurant",
  cafe: "cafe",
  coffee_shop: "cafe",
  bar: "bar",
  meal_takeaway: "fast_food",
  fast_food_restaurant: "fast_food",
  bank: "bank",
  atm: "atm",
  gas_station: "fuel",
  electric_vehicle_charging_station: "ev_charging",
  parking: "parking",
  school: "school",
  primary_school: "school",
  secondary_school: "school",
  university: "university",
  police: "police",
  fire_station: "fire_station",
  post_office: "post_office",
  library: "library",
  movie_theater: "cinema",
  performing_arts_theater: "theatre",
  museum: "museum",
  tourist_attraction: "attraction",
  lodging: "hotel",
  hotel: "hotel",
  park: "park",
  gym: "gym",
  fitness_center: "gym",
  supermarket: "supermarket",
  grocery_store: "supermarket",
  convenience_store: "convenience",
  bakery: "bakery",
  shopping_mall: "mall",
  department_store: "department_store",
  electronics_store: "electronics_store",
  clothing_store: "clothing_store",
  hair_salon: "hairdresser",
  laundry: "laundry",
  car_repair: "car_repair",
  place_of_worship: "place_of_worship",
  church: "place_of_worship",
  mosque: "place_of_worship",
  hindu_temple: "place_of_worship",
  synagogue: "place_of_worship",
};

/** 카테고리로서 의미 없는 일반 type — 매핑에서 제외한다 */
const GENERIC_TYPES = new Set([
  "point_of_interest",
  "establishment",
  "geocode",
  "political",
  "premise",
  "street_address",
  "route",
]);

/**
 * Google types 배열을 GeoWire 표준 카테고리 배열로 변환한다.
 * 매핑되면 표준값, 아니면 원본 type(일반 type은 제외). 중복은 제거한다.
 */
export function mapGoogleTypes(types: readonly string[] | undefined): string[] {
  const out = new Set<string>();
  for (const t of types ?? []) {
    if (GENERIC_TYPES.has(t)) continue;
    out.add(GOOGLE_CATEGORY_MAP[t] ?? t);
  }
  return [...out];
}
