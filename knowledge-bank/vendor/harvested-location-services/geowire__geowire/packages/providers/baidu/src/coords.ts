/**
 * 중국 좌표계 변환 — Baidu는 **BD-09**(百度坐标)로 좌표를 반환하지만 GeoWire 스키마는
 * WGS84다. 표준 공개 알고리즘으로 BD-09 → GCJ-02 → WGS84 변환한다.
 * (중국 경내 POI는 규정상 WGS84 출력이 불가하므로 클라이언트 변환이 필요.)
 */
const PI = Math.PI;
const X_PI = (PI * 3000) / 180;
const A = 6378245.0; // 장반경
const EE = 0.006_693_421_622_965_943; // 편심률 제곱

function outOfChina(lng: number, lat: number): boolean {
  return lng < 72.004 || lng > 137.8347 || lat < 0.8293 || lat > 55.8271;
}

function transformLat(lng: number, lat: number): number {
  let ret =
    -100 + 2 * lng + 3 * lat + 0.2 * lat * lat + 0.1 * lng * lat + 0.2 * Math.sqrt(Math.abs(lng));
  ret += ((20 * Math.sin(6 * lng * PI) + 20 * Math.sin(2 * lng * PI)) * 2) / 3;
  ret += ((20 * Math.sin(lat * PI) + 40 * Math.sin((lat / 3) * PI)) * 2) / 3;
  ret += ((160 * Math.sin((lat / 12) * PI) + 320 * Math.sin((lat * PI) / 30)) * 2) / 3;
  return ret;
}

function transformLng(lng: number, lat: number): number {
  let ret = 300 + lng + 2 * lat + 0.1 * lng * lng + 0.1 * lng * lat + 0.1 * Math.sqrt(Math.abs(lng));
  ret += ((20 * Math.sin(6 * lng * PI) + 20 * Math.sin(2 * lng * PI)) * 2) / 3;
  ret += ((20 * Math.sin(lng * PI) + 40 * Math.sin((lng / 3) * PI)) * 2) / 3;
  ret += ((150 * Math.sin((lng / 12) * PI) + 300 * Math.sin((lng / 30) * PI)) * 2) / 3;
  return ret;
}

/** BD-09 → GCJ-02 */
function bd09ToGcj02(bdLng: number, bdLat: number): [number, number] {
  const x = bdLng - 0.0065;
  const y = bdLat - 0.006;
  const z = Math.sqrt(x * x + y * y) - 0.00002 * Math.sin(y * X_PI);
  const theta = Math.atan2(y, x) - 0.000003 * Math.cos(x * X_PI);
  return [z * Math.cos(theta), z * Math.sin(theta)];
}

/** GCJ-02 → WGS84 (근사 역변환) */
function gcj02ToWgs84(gcjLng: number, gcjLat: number): [number, number] {
  if (outOfChina(gcjLng, gcjLat)) return [gcjLng, gcjLat];
  let dLat = transformLat(gcjLng - 105, gcjLat - 35);
  let dLng = transformLng(gcjLng - 105, gcjLat - 35);
  const radLat = (gcjLat / 180) * PI;
  let magic = Math.sin(radLat);
  magic = 1 - EE * magic * magic;
  const sqrtMagic = Math.sqrt(magic);
  dLat = (dLat * 180) / (((A * (1 - EE)) / (magic * sqrtMagic)) * PI);
  dLng = (dLng * 180) / (((A / sqrtMagic) * Math.cos(radLat)) * PI);
  const mgLat = gcjLat + dLat;
  const mgLng = gcjLng + dLng;
  return [gcjLng * 2 - mgLng, gcjLat * 2 - mgLat];
}

/** BD-09 좌표 → WGS84 {latitude, longitude} */
export function bd09ToWgs84(bdLng: number, bdLat: number): { latitude: number; longitude: number } {
  const [gcjLng, gcjLat] = bd09ToGcj02(bdLng, bdLat);
  const [wgsLng, wgsLat] = gcj02ToWgs84(gcjLng, gcjLat);
  return { latitude: wgsLat, longitude: wgsLng };
}
