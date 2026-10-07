import { readFile, writeFile, mkdir } from "node:fs/promises";
import { dirname } from "node:path";

/**
 * 디스크의 JSON 픽스처를 로드한다. CI는 픽스처만 쓰고 실외부호출을 하지 않는다는
 * 규약(설계 §4 테스트 계층)의 재생(replay) 쪽.
 */
export async function loadFixture<T = unknown>(filePath: string): Promise<T> {
  const raw = await readFile(filePath, "utf8");
  return JSON.parse(raw) as T;
}

/**
 * 픽스처를 기록한다 (record 모드: 실호출 응답을 저장해 이후 재생용으로 커밋).
 * 부모 디렉터리를 자동 생성하고 사람이 diff 하기 좋게 pretty-print 한다.
 */
export async function recordFixture(filePath: string, data: unknown): Promise<void> {
  await mkdir(dirname(filePath), { recursive: true });
  await writeFile(filePath, `${JSON.stringify(data, null, 2)}\n`, "utf8");
}
