export interface User {
  id: string;
  email: string;
  name: string;
  tier: 'free' | 'hobby' | 'pro' | 'enterprise';
  isActive: boolean;
  emailVerified: boolean;
  createdAt: Date;
  updatedAt: Date;
  lastLoginAt?: Date;
}

export interface ApiKey {
  id: string;
  userId: string;
  name: string;
  keyHash: string;
  keyPrefix: string;
  permissions: string[];
  rateLimit: RateLimit;
  isActive: boolean;
  lastUsedAt?: Date;
  createdAt: Date;
  expiresAt?: Date;
}

export interface RateLimit {
  requestsPerMinute: number;
  requestsPerHour: number;
  requestsPerDay: number;
  requestsPerMonth: number;
}

export interface UsageLog {
  id: string;
  userId?: string;
  apiKeyId?: string;
  endpoint: string;
  method: string;
  statusCode: number;
  responseTimeMs: number;
  requestSizeBytes: number;
  responseSizeBytes: number;
  ipAddress: string;
  userAgent: string;
  errorMessage?: string;
  createdAt: Date;
}

export interface SubscriptionPlan {
  id: string;
  name: string;
  tier: string;
  priceMonthly?: number;
  priceYearly?: number;
  rateLimit: RateLimit;
  features: string[];
  isActive: boolean;
  createdAt: Date;
}

export interface UserSubscription {
  id: string;
  userId: string;
  planId: string;
  status: 'active' | 'cancelled' | 'expired' | 'past_due';
  currentPeriodStart?: Date;
  currentPeriodEnd?: Date;
  stripeSubscriptionId?: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface JWTPayload {
  userId: string;
  email: string;
  tier: string;
  iat: number;
  exp: number;
}

import { Request } from 'express';

export interface AuthRequest extends Request {
  user?: User;
  apiKey?: ApiKey;
}

export interface CreateUserRequest {
  email: string;
  name: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface CreateApiKeyRequest {
  name: string;
  permissions?: string[];
  expiresAt?: Date;
}

export interface AuthResponse {
  success: boolean;
  user?: User;
  token?: string;
  apiKey?: Partial<ApiKey> & { key?: string };
  message?: string;
}

export interface RateLimitStatus {
  limit: number;
  remaining: number;
  resetTime: Date;
  windowType: 'minute' | 'hour' | 'day' | 'month';
}

export interface UsageStats {
  currentMonth: number;
  currentDay: number;
  currentHour: number;
  totalRequests: number;
  lastRequestAt?: Date;
}

export interface AuthConfig {
  jwtSecret: string;
  jwtExpiresIn: string;
  bcryptRounds: number;
  apiKeyLength: number;
  enableRegistration: boolean;
  requireEmailVerification: boolean;
} 