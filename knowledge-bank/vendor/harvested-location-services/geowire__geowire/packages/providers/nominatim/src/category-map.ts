/**
 * OSM `category:type` → GeoWire 표준 카테고리 매핑 (설계 §7.3 카테고리 평탄화).
 * 커뮤니티 PR로 확장하는 데이터 파일이다 (good-first-issue). v0.1은 ~50개로 시작.
 * 매핑에 없으면 원본 `type`을 그대로 카테고리로 쓴다.
 */
export const CATEGORY_MAP: Record<string, string> = {
  // amenity
  "amenity:pharmacy": "pharmacy",
  "amenity:hospital": "hospital",
  "amenity:clinic": "clinic",
  "amenity:doctors": "doctor",
  "amenity:dentist": "dentist",
  "amenity:restaurant": "restaurant",
  "amenity:cafe": "cafe",
  "amenity:bar": "bar",
  "amenity:pub": "bar",
  "amenity:fast_food": "fast_food",
  "amenity:food_court": "fast_food",
  "amenity:bank": "bank",
  "amenity:atm": "atm",
  "amenity:fuel": "fuel",
  "amenity:charging_station": "ev_charging",
  "amenity:parking": "parking",
  "amenity:school": "school",
  "amenity:kindergarten": "school",
  "amenity:university": "university",
  "amenity:college": "university",
  "amenity:police": "police",
  "amenity:fire_station": "fire_station",
  "amenity:post_office": "post_office",
  "amenity:library": "library",
  "amenity:cinema": "cinema",
  "amenity:theatre": "theatre",
  "amenity:place_of_worship": "place_of_worship",
  "amenity:marketplace": "marketplace",
  "amenity:townhall": "government",
  // shop
  "shop:supermarket": "supermarket",
  "shop:convenience": "convenience",
  "shop:bakery": "bakery",
  "shop:hairdresser": "hairdresser",
  "shop:laundry": "laundry",
  "shop:car_repair": "car_repair",
  "shop:clothes": "clothing_store",
  "shop:mall": "mall",
  "shop:department_store": "department_store",
  "shop:electronics": "electronics_store",
  "shop:convenience_store": "convenience",
  "shop:coffee": "cafe",
  // tourism
  "tourism:hotel": "hotel",
  "tourism:guest_house": "hotel",
  "tourism:hostel": "hotel",
  "tourism:motel": "hotel",
  "tourism:museum": "museum",
  "tourism:attraction": "attraction",
  "tourism:viewpoint": "attraction",
  // leisure
  "leisure:park": "park",
  "leisure:garden": "park",
  "leisure:fitness_centre": "gym",
  "leisure:sports_centre": "gym",
  // healthcare
  "healthcare:pharmacy": "pharmacy",
  "healthcare:hospital": "hospital",
  "healthcare:clinic": "clinic",
  "healthcare:doctor": "doctor",
  // office
  "office:government": "government",
};

/**
 * OSM (category, type) 쌍을 GeoWire 카테고리 배열로 변환한다.
 * 매핑에 있으면 표준 카테고리, 없으면 원본 type, 둘 다 없으면 빈 배열.
 */
export function mapCategory(category?: string, type?: string): string[] {
  if (category && type) {
    const mapped = CATEGORY_MAP[`${category}:${type}`];
    if (mapped) return [mapped];
  }
  if (type) return [type];
  return [];
}
