import { readFileSync } from "node:fs";
import { defineProvider, type GeoProvider } from "@geowirehq/provider-sdk";
import type { SearchPlacesRequest } from "@geowirehq/schema";
import { INTERNAL_MANIFEST } from "./manifest.js";
import { parseCsvRecords } from "./csv.js";
import { StoreIndex } from "./store.js";

export interface InternalOptions {
  /** CSV 파일 경로. 지정 시 동기 로드한다 */
  source?: string;
  /** CSV 텍스트 직접 주입(파일 대신) */
  csv?: string;
  /** 이미 파싱된 레코드 직접 주입(테스트·프로그래매틱 사용) */
  records?: Record<string, string>[];
  /** 공급자 id 오버라이드(여러 자체 소스 구분용). 기본 "internal" */
  id?: string;
  /** 표시 이름 오버라이드 */
  name?: string;
}

/**
 * 고객 자체 데이터(CSV) 공급자를 만든다 (설계 §5 internal).
 * `source`(파일 경로) / `csv`(텍스트) / `records`(파싱된 배열) 중 하나로 데이터를 받는다.
 * 인메모리 이름 부분일치 + Haversine 반경 검색을 제공하며 API 키가 필요 없다.
 */
export function createInternalProvider(options: InternalOptions = {}): GeoProvider {
  const records = resolveRecords(options);
  const index = new StoreIndex(records);

  const manifest =
    options.id || options.name
      ? { ...INTERNAL_MANIFEST, id: options.id ?? INTERNAL_MANIFEST.id, name: options.name ?? INTERNAL_MANIFEST.name }
      : INTERNAL_MANIFEST;

  return defineProvider({
    manifest,
    async searchPlaces(req: SearchPlacesRequest) {
      return index.search(req);
    },
  });
}

function resolveRecords(options: InternalOptions): Record<string, string>[] {
  if (options.records) return options.records;
  if (options.csv != null) return parseCsvRecords(options.csv);
  if (options.source) return parseCsvRecords(readFileSync(options.source, "utf8"));
  return [];
}
