import type {
  IsochroneRequest,
  Isochrone,
  LatLng,
  ResponseMeta,
  TravelMode,
} from "@geowirehq/schema";
import { runDistanceMatrix } from "../pipeline/routing.js";
import type { PipelineHost } from "../pipeline/pipeline.js";

const EARTH_R = 6_371_000;
const D2R = Math.PI / 180;
const R2D = 180 / Math.PI;

/** 이동수단별 최대 반경 추정 속도(m/s) — 표본 격자 범위 산정용(도로 우회로 실제 프론티어는 안쪽) */
const SPEED_MPS: Record<TravelMode, number> = {
  driving: 16.7, // ~60 km/h
  walking: 1.5,
  cycling: 4.5,
};

const NOTE =
  "approximate isochrone — sampled bearings scored by a distance matrix, not a true reachability engine";

/** 출발점에서 bearing(도)·distance(m) 떨어진 지점 (구면 전진 공식) */
function destinationPoint(o: LatLng, bearingDeg: number, distanceM: number): LatLng {
  const δ = distanceM / EARTH_R;
  const θ = bearingDeg * D2R;
  const φ1 = o.latitude * D2R;
  const λ1 = o.longitude * D2R;
  const sinφ2 = Math.sin(φ1) * Math.cos(δ) + Math.cos(φ1) * Math.sin(δ) * Math.cos(θ);
  const φ2 = Math.asin(Math.min(1, Math.max(-1, sinφ2)));
  const λ2 =
    λ1 + Math.atan2(Math.sin(θ) * Math.sin(δ) * Math.cos(φ1), Math.cos(δ) - Math.sin(φ1) * sinφ2);
  return { latitude: φ2 * R2D, longitude: ((λ2 * R2D + 540) % 360) - 180 };
}

/** 폴리곤(경도,위도 링) 면적 km² — 출발점 기준 등거리 투영 + 신발끈 공식 */
function polygonAreaSqKm(ring: Array<[number, number]>, origin: LatLng): number {
  const cosLat = Math.cos(origin.latitude * D2R);
  const pts: Array<[number, number]> = ring.map(([lng, lat]) => [
    (lng - origin.longitude) * D2R * EARTH_R * cosLat,
    (lat - origin.latitude) * D2R * EARTH_R,
  ]);
  let sum = 0;
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i]!;
    const b = pts[(i + 1) % pts.length]!;
    sum += a[0] * b[1] - b[0] * a[1];
  }
  return Math.abs(sum) / 2 / 1_000_000;
}

/**
 * 도달권(isochrone) 근사 (설계: isochrone/v1).
 * 방위 B개 × 반경 K단계로 표본점을 만들고, distanceMatrix 공급자(무키 OSRM 등)로
 * 출발점→각 표본 이동시간을 구한 뒤, 방위별로 예산 내 가장 먼 표본을 프론티어로 이어 폴리곤을 만든다.
 * 전용 도달권 엔진이 아니라 거리행렬 위에 쌓은 근사다(무키·라이브 검증 가능).
 */
export async function runIsochrone(
  host: PipelineHost,
  req: IsochroneRequest,
): Promise<{ isochrone: Isochrone | null; meta: ResponseMeta }> {
  const budgetSec = req.minutes * 60;
  const maxRadius = SPEED_MPS[req.mode] * budgetSec * 1.15; // 여유 15%
  // OSRM table 좌표 상한(≈100) 안에서 표본 수 제한
  const radiiCount = Math.max(3, Math.min(6, Math.floor(90 / req.bearings)));

  // 방위 × 반경 표본점 생성 (순서: bearing 바깥루프, radius 안쪽루프)
  const samples: LatLng[] = [];
  for (let b = 0; b < req.bearings; b++) {
    const bearing = (360 / req.bearings) * b;
    for (let r = 1; r <= radiiCount; r++) {
      samples.push(destinationPoint(req.origin, bearing, (maxRadius * r) / radiiCount));
    }
  }

  const { matrix, meta } = await runDistanceMatrix(host, {
    origins: [req.origin],
    destinations: samples,
    mode: req.mode,
    options: req.options,
  });
  if (!matrix) return { isochrone: null, meta };

  const row = matrix.rows[0] ?? [];
  let reachable = 0;
  const ring: Array<[number, number]> = [];
  for (let b = 0; b < req.bearings; b++) {
    let frontier: LatLng | null = null;
    // 안쪽→바깥 순회하며 예산 내 가장 먼 표본을 찾는다
    for (let r = 1; r <= radiiCount; r++) {
      const idx = b * radiiCount + (r - 1);
      const cell = row[idx];
      if (cell?.durationSeconds != null && cell.durationSeconds <= budgetSec) {
        frontier = samples[idx]!;
        reachable++;
      }
    }
    const bearing = (360 / req.bearings) * b;
    // 도달 표본이 없으면 출발점 근처에 작은 점(폴리곤 붕괴 방지)
    const p = frontier ?? destinationPoint(req.origin, bearing, maxRadius / radiiCount / 4);
    ring.push([p.longitude, p.latitude]);
  }
  ring.push(ring[0]!); // 링 닫기

  const isochrone: Isochrone = {
    origin: req.origin,
    mode: req.mode,
    minutes: req.minutes,
    polygon: { type: "Polygon", coordinates: [ring] },
    areaSqKm: Math.round(polygonAreaSqKm(ring, req.origin) * 100) / 100,
    reachableSamples: reachable,
    sampleCount: samples.length,
    provider: matrix.provider,
    attributions: matrix.attributions,
    note: NOTE,
  };
  return { isochrone, meta };
}
