/**
 * Kakao `category_group_code` → GeoWire 표준 카테고리 매핑.
 * 카카오 그룹 코드는 18종으로 고정 (Local API 문서). 커뮤니티 PR로 확장 가능.
 */
export const KAKAO_GROUP_MAP: Record<string, string> = {
  MT1: "supermarket", // 대형마트
  CS2: "convenience", // 편의점
  PS3: "childcare", // 어린이집·유치원
  SC4: "school", // 학교
  AC5: "academy", // 학원
  PK6: "parking", // 주차장
  OL7: "gas_station", // 주유소·충전소
  SW8: "subway_station", // 지하철역
  BK9: "bank", // 은행
  CT1: "culture", // 문화시설
  AG2: "real_estate", // 중개업소
  PO3: "public_office", // 공공기관
  AT4: "attraction", // 관광명소
  AD5: "lodging", // 숙박
  FD6: "restaurant", // 음식점
  CE7: "cafe", // 카페
  HP8: "hospital", // 병원
  PM9: "pharmacy", // 약국
};

/**
 * 그룹 코드로 표준 카테고리를, 그리고 `category_name`("음식점 > 카페 > 커피전문점")의
 * 마지막 세그먼트를 부가 카테고리로 덧붙인다. 둘 다 없으면 빈 배열.
 */
export function mapKakaoCategory(groupCode?: string, categoryName?: string): string[] {
  const cats: string[] = [];
  if (groupCode && KAKAO_GROUP_MAP[groupCode]) cats.push(KAKAO_GROUP_MAP[groupCode]);
  if (categoryName) {
    const last = categoryName
      .split(">")
      .map((s) => s.trim())
      .filter(Boolean)
      .pop();
    if (last && !cats.includes(last)) cats.push(last);
  }
  return cats;
}
