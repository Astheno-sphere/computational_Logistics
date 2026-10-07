import { Response, NextFunction } from 'express';
import { createClient, RedisClientType } from 'redis';
import { Pool } from 'pg';
import type { AuthRequest, RateLimit, RateLimitStatus, UsageLog } from '../auth/auth-types.js';

export interface RateLimitConfig {
  redis?: {
    url: string;
    enabled: boolean;
  };
  postgres: {
    pool: Pool;
  };
  defaultLimits: RateLimit;
  enableUsageTracking: boolean;
  enableAnalytics: boolean;
}

export class RateLimitService {
  private redis?: RedisClientType;
  private db: Pool;
  private config: RateLimitConfig;

  constructor(config: RateLimitConfig) {
    this.config = config;
    this.db = config.postgres.pool;

    // Initialize Redis if enabled
    if (config.redis?.enabled && config.redis.url) {
      this.redis = createClient({ url: config.redis.url });
      this.redis.on('error', (err) => console.error('Redis Client Error:', err));
      this.redis.connect().catch(console.error);
    }
  }

  // Main rate limiting middleware
  rateLimitMiddleware = async (req: AuthRequest, res: Response, next: NextFunction) => {
    try {
      // Skip rate limiting if disabled or no user/api key
      if (!this.config.redis?.enabled && !this.db) {
        return next();
      }

      const startTime = Date.now();
      const rateLimits = this.getRateLimitsForRequest(req);
      
      // Check all rate limit windows
      const limitChecks = await Promise.all([
        this.checkRateLimit(req, rateLimits, 'minute'),
        this.checkRateLimit(req, rateLimits, 'hour'),
        this.checkRateLimit(req, rateLimits, 'day'),
        this.checkRateLimit(req, rateLimits, 'month')
      ]);

      // Find the most restrictive limit that's exceeded
      const exceededLimit = limitChecks.find(check => !check.allowed);
      
      if (exceededLimit) {
        // Log the rate limit violation
        if (this.config.enableUsageTracking) {
          await this.logUsage(req, {
            statusCode: 429,
            responseTimeMs: Date.now() - startTime,
            errorMessage: `Rate limit exceeded: ${exceededLimit.windowType}`
          });
        }

        return res.status(429).json({
          error: 'Too Many Requests',
          message: `Rate limit exceeded for ${exceededLimit.windowType}`,
          rateLimit: {
            limit: exceededLimit.limit,
            remaining: exceededLimit.remaining,
            resetTime: exceededLimit.resetTime,
            windowType: exceededLimit.windowType
          },
          retryAfter: Math.ceil((exceededLimit.resetTime.getTime() - Date.now()) / 1000)
        });
      }

      // Increment counters for all windows
      await Promise.all([
        this.incrementCounter(req, 'minute'),
        this.incrementCounter(req, 'hour'),
        this.incrementCounter(req, 'day'),
        this.incrementCounter(req, 'month')
      ]);

      // Add rate limit headers
      const rateLimitHeaders = this.formatRateLimitHeaders(limitChecks);
      Object.entries(rateLimitHeaders).forEach(([key, value]) => {
        res.setHeader(key, value);
      });

      // Track request start time for usage logging
      (req as any).startTime = startTime;

      next();
    } catch (error) {
      console.error('Rate limiting error:', error);
      // Continue without rate limiting if there's an error
      next();
    }
  };

  // Usage tracking middleware (to be called after response)
  usageTrackingMiddleware = async (req: AuthRequest, res: Response, next: NextFunction) => {
    if (!this.config.enableUsageTracking) {
      return next();
    }

    const startTime = (req as any).startTime || Date.now();
    const logUsageMethod = this.logUsage.bind(this);

    // Override res.end to capture response data
    const originalEnd = res.end;
    const originalWrite = res.write;
    let responseSize = 0;

    res.write = function(chunk: any, ...args: any[]) {
      if (chunk) {
        responseSize += Buffer.isBuffer(chunk) ? chunk.length : Buffer.byteLength(chunk);
      }
      return originalWrite.apply(this, [chunk, args[0], args[1]] as any);
    };

    res.end = function(this: any, chunk: any, ...args: any[]) {
      if (chunk) {
        responseSize += Buffer.isBuffer(chunk) ? chunk.length : Buffer.byteLength(chunk);
      }

      // Log usage after response is sent
      setImmediate(async () => {
        try {
          await logUsageMethod(req, {
            statusCode: res.statusCode,
            responseTimeMs: Date.now() - startTime,
            responseSizeBytes: responseSize
          });
        } catch (error) {
          console.error('Usage logging error:', error);
        }
      });

      return originalEnd.apply(this, [chunk, args[0], args[1]] as any);
    };

    next();
  };

  private async checkRateLimit(
    req: AuthRequest, 
    rateLimits: RateLimit, 
    windowType: 'minute' | 'hour' | 'day' | 'month'
  ): Promise<RateLimitStatus & { allowed: boolean }> {
    const limit = this.getLimitForWindow(rateLimits, windowType);
    const keyId = this.getKeyId(req);
    const windowStart = this.getWindowStart(windowType);
    const resetTime = this.getWindowEnd(windowType);

    let currentCount = 0;

    try {
      if (this.redis) {
        // Use Redis for fast rate limiting
        currentCount = await this.getRedisCount(keyId, windowType, windowStart);
      } else {
        // Fallback to database
        currentCount = await this.getDatabaseCount(keyId, windowType, windowStart);
      }
    } catch (error) {
      console.error(`Error checking rate limit for ${windowType}:`, error);
      // Allow request if we can't check rate limit
      return {
        limit,
        remaining: limit,
        resetTime,
        windowType,
        allowed: true
      };
    }

    const remaining = Math.max(0, limit - currentCount);
    const allowed = currentCount < limit;

    return {
      limit,
      remaining,
      resetTime,
      windowType,
      allowed
    };
  }

  private async incrementCounter(req: AuthRequest, windowType: 'minute' | 'hour' | 'day' | 'month'): Promise<void> {
    const keyId = this.getKeyId(req);
    const windowStart = this.getWindowStart(windowType);

    try {
      if (this.redis) {
        await this.incrementRedisCounter(keyId, windowType, windowStart);
      } else {
        await this.incrementDatabaseCounter(keyId, windowType, windowStart);
      }
    } catch (error) {
      console.error(`Error incrementing counter for ${windowType}:`, error);
    }
  }

  private async getRedisCount(keyId: string, windowType: string, windowStart: Date): Promise<number> {
    if (!this.redis) return 0;
    
    const key = `rate_limit:${keyId}:${windowType}:${windowStart.getTime()}`;
    const count = await this.redis.get(key);
    return count ? parseInt(count, 10) : 0;
  }

  private async incrementRedisCounter(keyId: string, windowType: string, windowStart: Date): Promise<void> {
    if (!this.redis) return;

    const key = `rate_limit:${keyId}:${windowType}:${windowStart.getTime()}`;
    const ttl = this.getWindowTTL(windowType);
    
    const multi = this.redis.multi();
    multi.incr(key);
    multi.expire(key, ttl);
    await multi.exec();
  }

  private async getDatabaseCount(keyId: string, windowType: string, windowStart: Date): Promise<number> {
    const query = `
      SELECT request_count
      FROM rate_limits
      WHERE api_key_id = $1 AND window_type = $2 AND window_start = $3
    `;

    const result = await this.db.query(query, [keyId, windowType, windowStart]);
    return result.rows.length > 0 ? result.rows[0].request_count : 0;
  }

  private async incrementDatabaseCounter(keyId: string, windowType: string, windowStart: Date): Promise<void> {
    const query = `
      INSERT INTO rate_limits (api_key_id, window_type, window_start, request_count)
      VALUES ($1, $2, $3, 1)
      ON CONFLICT (api_key_id, window_type, window_start)
      DO UPDATE SET request_count = rate_limits.request_count + 1
    `;

    await this.db.query(query, [keyId, windowType, windowStart]);
  }

  private async logUsage(req: AuthRequest, additionalData: Partial<UsageLog> = {}): Promise<void> {
    try {
      const requestSize = req.get('content-length') ? parseInt(req.get('content-length')!, 10) : 0;
      
      const usageData = {
        userId: req.user?.id || null,
        apiKeyId: req.apiKey?.id || null,
        endpoint: req.path,
        method: req.method,
        ipAddress: req.ip || req.connection.remoteAddress || 'unknown',
        userAgent: req.get('user-agent') || 'unknown',
        requestSizeBytes: requestSize,
        responseSizeBytes: 0,
        responseTimeMs: 0,
        statusCode: 200,
        ...additionalData
      };

      const query = `
        INSERT INTO usage_logs (
          user_id, api_key_id, endpoint, method, status_code, 
          response_time_ms, request_size_bytes, response_size_bytes,
          ip_address, user_agent, error_message
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
      `;

      await this.db.query(query, [
        usageData.userId,
        usageData.apiKeyId,
        usageData.endpoint,
        usageData.method,
        usageData.statusCode,
        usageData.responseTimeMs,
        usageData.requestSizeBytes,
        usageData.responseSizeBytes,
        usageData.ipAddress,
        usageData.userAgent,
        usageData.errorMessage || null
      ]);
    } catch (error) {
      console.error('Usage logging error:', error);
    }
  }

  private getRateLimitsForRequest(req: AuthRequest): RateLimit {
    // Use API key limits if available, otherwise use default limits
    if (req.apiKey?.rateLimit) {
      return req.apiKey.rateLimit;
    }

    // Use tier-based limits if user is authenticated
    if (req.user?.tier) {
      return this.getTierLimits(req.user.tier);
    }

    // Use default limits for unauthenticated requests
    return this.config.defaultLimits;
  }

  private getTierLimits(tier: string): RateLimit {
    const tierLimits: Record<string, RateLimit> = {
      free: {
        requestsPerMinute: 10,
        requestsPerHour: 100,
        requestsPerDay: 1000,
        requestsPerMonth: 1000
      },
      hobby: {
        requestsPerMinute: 100,
        requestsPerHour: 1000,
        requestsPerDay: 10000,
        requestsPerMonth: 50000
      },
      pro: {
        requestsPerMinute: 1000,
        requestsPerHour: 10000,
        requestsPerDay: 100000,
        requestsPerMonth: 500000
      },
      enterprise: {
        requestsPerMinute: 10000,
        requestsPerHour: 100000,
        requestsPerDay: 1000000,
        requestsPerMonth: -1 // Unlimited
      }
    };

    return tierLimits[tier] || this.config.defaultLimits;
  }

  private getLimitForWindow(rateLimits: RateLimit, windowType: 'minute' | 'hour' | 'day' | 'month'): number {
    const mapping: Record<string, keyof RateLimit> = {
      'minute': 'requestsPerMinute',
      'hour': 'requestsPerHour', 
      'day': 'requestsPerDay',
      'month': 'requestsPerMonth'
    };
    const limit = rateLimits[mapping[windowType]];
    return limit === -1 ? Number.MAX_SAFE_INTEGER : limit;
  }

  private getKeyId(req: AuthRequest): string {
    // Use API key ID if available, otherwise use user ID, otherwise use IP
    return req.apiKey?.id || req.user?.id || req.ip || 'anonymous';
  }

  private getWindowStart(windowType: 'minute' | 'hour' | 'day' | 'month'): Date {
    const now = new Date();
    
    switch (windowType) {
      case 'minute':
        return new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours(), now.getMinutes());
      case 'hour':
        return new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours());
      case 'day':
        return new Date(now.getFullYear(), now.getMonth(), now.getDate());
      case 'month':
        return new Date(now.getFullYear(), now.getMonth());
      default:
        return now;
    }
  }

  private getWindowEnd(windowType: 'minute' | 'hour' | 'day' | 'month'): Date {
    const windowStart = this.getWindowStart(windowType);
    
    switch (windowType) {
      case 'minute':
        return new Date(windowStart.getTime() + 60 * 1000);
      case 'hour':
        return new Date(windowStart.getTime() + 60 * 60 * 1000);
      case 'day':
        return new Date(windowStart.getTime() + 24 * 60 * 60 * 1000);
      case 'month': {
        const nextMonth = new Date(windowStart);
        nextMonth.setMonth(nextMonth.getMonth() + 1);
        return nextMonth;
      }
      default:
        return new Date(windowStart.getTime() + 60 * 1000);
    }
  }

  private getWindowTTL(windowType: string): number {
    switch (windowType) {
      case 'minute': return 60;
      case 'hour': return 3600;
      case 'day': return 86400;
      case 'month': return 2592000; // 30 days
      default: return 60;
    }
  }

  private formatRateLimitHeaders(limitChecks: (RateLimitStatus & { allowed: boolean })[]): Record<string, string> {
    const headers: Record<string, string> = {};

    limitChecks.forEach(check => {
      const prefix = `X-RateLimit-${check.windowType.charAt(0).toUpperCase() + check.windowType.slice(1)}`;
      headers[`${prefix}-Limit`] = check.limit.toString();
      headers[`${prefix}-Remaining`] = check.remaining.toString();
      headers[`${prefix}-Reset`] = Math.ceil(check.resetTime.getTime() / 1000).toString();
    });

    return headers;
  }

  // Utility methods for analytics
  async getUserUsageStats(userId: string, timeframe: 'day' | 'week' | 'month' = 'month'): Promise<any> {
    const interval = timeframe === 'day' ? '1 day' : timeframe === 'week' ? '7 days' : '30 days';
    
    const query = `
      SELECT 
        DATE_TRUNC('hour', created_at) as hour,
        COUNT(*) as requests,
        AVG(response_time_ms) as avg_response_time,
        SUM(request_size_bytes + response_size_bytes) as total_bytes
      FROM usage_logs
      WHERE user_id = $1 AND created_at >= NOW() - INTERVAL '${interval}'
      GROUP BY DATE_TRUNC('hour', created_at)
      ORDER BY hour
    `;

    const result = await this.db.query(query, [userId]);
    return result.rows;
  }

  async getSystemUsageStats(timeframe: 'day' | 'week' | 'month' = 'day'): Promise<any> {
    const interval = timeframe === 'day' ? '1 day' : timeframe === 'week' ? '7 days' : '30 days';
    
    const query = `
      SELECT 
        DATE_TRUNC('hour', created_at) as hour,
        COUNT(*) as total_requests,
        COUNT(DISTINCT user_id) as unique_users,
        AVG(response_time_ms) as avg_response_time,
        SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as error_count,
        SUM(request_size_bytes + response_size_bytes) as total_bytes
      FROM usage_logs
      WHERE created_at >= NOW() - INTERVAL '${interval}'
      GROUP BY DATE_TRUNC('hour', created_at)
      ORDER BY hour
    `;

    const result = await this.db.query(query);
    return result.rows;
  }

  async cleanup(): Promise<void> {
    if (this.redis) {
      await this.redis.quit();
    }
  }
} 