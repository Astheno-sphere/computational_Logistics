/**
 * 최소 간격 rate limiter — 공용 Nominatim 서버 예절(1 req/s)을 **provider 내부에서 강제**한다.
 * OSM 커뮤니티와의 신뢰는 이 프로젝트의 평판 자산이므로 호출자가 끌 수 없게 한다 (설계 §10, §7.1).
 *
 * `now`는 acquire마다 주입받고(테스트 결정성), `sleep`은 생성자에서 주입한다.
 */
export class RateLimiter {
  private nextAvailable = 0;

  constructor(
    private readonly intervalMs: number,
    private readonly sleep: (ms: number) => Promise<void>,
  ) {}

  /** 다음 호출이 허용될 때까지 대기한다. 최소 `intervalMs` 간격을 보장한다. */
  async acquire(now: number): Promise<void> {
    const waitMs = Math.max(0, this.nextAvailable - now);
    this.nextAvailable = Math.max(now, this.nextAvailable) + this.intervalMs;
    if (waitMs > 0) await this.sleep(waitMs);
  }
}
