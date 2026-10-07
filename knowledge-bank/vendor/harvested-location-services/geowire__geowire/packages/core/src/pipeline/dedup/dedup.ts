import type { Place } from "@geowirehq/schema";
import { pairScore } from "./similarity.js";
import { mergeCluster, type MergeContext } from "./merge-fields.js";

/**
 * 후보 프리필터용 격자 셀 크기(도). 약 1.1km — 근접 신호 컷오프(500m)보다 넉넉히 잡아
 * 셀 경계에 걸친 동일 장소를 놓치지 않는다(이웃 8셀까지 후보에 포함).
 * geohash prefix grouping의 등가 구현 — O(n²)를 회피하는 버킷팅이다(설계 §7.3).
 */
const CELL_DEG = 0.01;

export interface DedupOptions extends MergeContext {
  /** 이 점수 이상이면 병합 (기본 0.75) */
  mergeThreshold: number;
}

export interface DedupResult {
  merged: Place[];
  before: number;
  after: number;
}

/** 좌표를 격자 셀 키로 (자신 + 8이웃 후보 생성에 사용) */
function cellCoord(lat: number, lon: number): [number, number] {
  return [Math.floor(lat / CELL_DEG), Math.floor(lon / CELL_DEG)];
}

class UnionFind {
  private readonly parent: number[];
  constructor(n: number) {
    this.parent = Array.from({ length: n }, (_, i) => i);
  }
  find(i: number): number {
    let root = i;
    while (this.parent[root] !== root) root = this.parent[root]!;
    while (this.parent[i] !== root) {
      const next = this.parent[i]!;
      this.parent[i] = root;
      i = next;
    }
    return root;
  }
  union(a: number, b: number): void {
    const ra = this.find(a);
    const rb = this.find(b);
    if (ra !== rb) this.parent[Math.max(ra, rb)] = Math.min(ra, rb);
  }
}

/**
 * 중복 장소를 병합한다 (설계 §7.3).
 * 격자 버킷팅으로 후보 쌍을 좁히고, `mergeThreshold` 이상인 쌍을 union-find로 묶어
 * 각 클러스터를 `mergeCluster`로 하나의 Place로 합친다.
 * 입력 순서 안정성: 각 클러스터는 가장 앞선 원소의 위치에 놓인다.
 */
export function dedup(places: Place[], opts: DedupOptions): DedupResult {
  const before = places.length;
  if (before <= 1) return { merged: [...places], before, after: before };

  // 셀 → 인덱스 버킷
  const buckets = new Map<string, number[]>();
  const coords = places.map((p) => cellCoord(p.location.latitude, p.location.longitude));
  coords.forEach(([cx, cy], i) => {
    const key = `${cx}:${cy}`;
    (buckets.get(key) ?? buckets.set(key, []).get(key)!).push(i);
  });

  const uf = new UnionFind(before);
  for (let i = 0; i < before; i++) {
    const [cx, cy] = coords[i]!;
    for (let dx = -1; dx <= 1; dx++) {
      for (let dy = -1; dy <= 1; dy++) {
        const neighbors = buckets.get(`${cx + dx}:${cy + dy}`);
        if (!neighbors) continue;
        for (const j of neighbors) {
          if (j <= i) continue;
          if (pairScore(places[i]!, places[j]!) >= opts.mergeThreshold) uf.union(i, j);
        }
      }
    }
  }

  // 클러스터 수집 (대표 인덱스 = 최소 인덱스, 입력 순서 보존)
  const clusters = new Map<number, Place[]>();
  for (let i = 0; i < before; i++) {
    const root = uf.find(i);
    (clusters.get(root) ?? clusters.set(root, []).get(root)!).push(places[i]!);
  }

  const merged = [...clusters.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([, cluster]) => mergeCluster(cluster, opts));

  return { merged, before, after: merged.length };
}
