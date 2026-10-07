export type GatewayRuntimeStats = {
  startedAt: string;
  uptimeMs: number;
  totalRequests: number;
  successfulRequests: number;
  failedRequests: number;
  activeConnections: number;
  successRate: number;
};

export class GatewayRuntimeStatsTracker {
  private startedAt = Date.now();
  private totalRequests = 0;
  private successfulRequests = 0;
  private failedRequests = 0;
  private activeConnections = 0;

  reset(): void {
    this.startedAt = Date.now();
    this.totalRequests = 0;
    this.successfulRequests = 0;
    this.failedRequests = 0;
    this.activeConnections = 0;
  }

  onRequestStart(): void {
    this.totalRequests += 1;
    this.activeConnections += 1;
  }

  onRequestEnd(success: boolean): void {
    this.activeConnections = Math.max(0, this.activeConnections - 1);
    if (success) {
      this.successfulRequests += 1;
    } else {
      this.failedRequests += 1;
    }
  }

  snapshot(now = Date.now()): GatewayRuntimeStats {
    const total = this.totalRequests;
    const successRate = total > 0 ? Math.round((this.successfulRequests / total) * 1000) / 10 : 100;
    return {
      startedAt: new Date(this.startedAt).toISOString(),
      uptimeMs: Math.max(0, now - this.startedAt),
      totalRequests: total,
      successfulRequests: this.successfulRequests,
      failedRequests: this.failedRequests,
      activeConnections: this.activeConnections,
      successRate,
    };
  }
}
