import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import crypto from 'crypto';
import { Pool } from 'pg';
import type {
  User,
  ApiKey,
  CreateUserRequest,
  LoginRequest,
  CreateApiKeyRequest,
  AuthResponse,
  JWTPayload,
  AuthConfig,
  RateLimit,
  SubscriptionPlan
} from './auth-types.js';

export class AuthService {
  private db: Pool;
  private config: AuthConfig;

  constructor(db: Pool, config: AuthConfig) {
    this.db = db;
    this.config = config;
  }

  // User Authentication Methods
  async register(userData: CreateUserRequest): Promise<AuthResponse> {
    try {
      // Check if user already exists
      const existingUser = await this.getUserByEmail(userData.email);
      if (existingUser) {
        return {
          success: false,
          message: 'User with this email already exists'
        };
      }

      // Hash password
      const passwordHash = await bcrypt.hash(userData.password, this.config.bcryptRounds);

      // Create user
      const query = `
        INSERT INTO users (email, name, password_hash)
        VALUES ($1, $2, $3)
        RETURNING id, email, name, tier, is_active, email_verified, created_at, updated_at
      `;

      const result = await this.db.query(query, [
        userData.email,
        userData.name,
        passwordHash
      ]);

      const user = this.mapDbUserToUser(result.rows[0]);

      // Create default API key
      const defaultApiKey = await this.createApiKey(user.id, {
        name: 'Default API Key'
      });

      // Generate JWT token
      const token = this.generateJWT(user);

      return {
        success: true,
        user,
        token,
        apiKey: defaultApiKey || undefined,
        message: 'User registered successfully'
      };
    } catch (error) {
      console.error('Registration error:', error);
      return {
        success: false,
        message: 'Failed to register user'
      };
    }
  }

  async login(loginData: LoginRequest): Promise<AuthResponse> {
    try {
      // Get user with password hash
      const query = `
        SELECT id, email, name, password_hash, tier, is_active, email_verified, created_at, updated_at, last_login_at
        FROM users
        WHERE email = $1 AND is_active = true
      `;

      const result = await this.db.query(query, [loginData.email]);

      if (result.rows.length === 0) {
        return {
          success: false,
          message: 'Invalid email or password'
        };
      }

      const dbUser = result.rows[0];

      // Verify password
      const isPasswordValid = await bcrypt.compare(loginData.password, dbUser.password_hash);
      if (!isPasswordValid) {
        return {
          success: false,
          message: 'Invalid email or password'
        };
      }

      // Update last login
      await this.db.query(
        'UPDATE users SET last_login_at = NOW() WHERE id = $1',
        [dbUser.id]
      );

      const user = this.mapDbUserToUser(dbUser);
      const token = this.generateJWT(user);

      return {
        success: true,
        user,
        token,
        message: 'Login successful'
      };
    } catch (error) {
      console.error('Login error:', error);
      return {
        success: false,
        message: 'Failed to login'
      };
    }
  }

  async verifyJWT(token: string): Promise<User | null> {
    try {
      const payload = jwt.verify(token, this.config.jwtSecret) as JWTPayload;
      return await this.getUserById(payload.userId);
    } catch (error) {
      return null;
    }
  }

  // API Key Management
  async createApiKey(userId: string, keyData: CreateApiKeyRequest): Promise<(Partial<ApiKey> & { key?: string }) | null> {
    try {
      // Get user's subscription plan for rate limits
      const userPlan = await this.getUserSubscriptionPlan(userId);
      const rateLimit: RateLimit = userPlan?.rateLimit || {
        requestsPerMinute: 10,
        requestsPerHour: 100,
        requestsPerDay: 1000,
        requestsPerMonth: 1000
      };

      // Generate API key
      const apiKey = this.generateApiKey();
      const keyHash = await bcrypt.hash(apiKey, this.config.bcryptRounds);
      const keyPrefix = `osm_${apiKey.substring(0, 8)}`;

      const query = `
        INSERT INTO api_keys (user_id, name, key_hash, key_prefix, permissions, rate_limit, expires_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id, name, key_prefix, permissions, rate_limit, is_active, created_at, expires_at
      `;

      const result = await this.db.query(query, [
        userId,
        keyData.name,
        keyHash,
        keyPrefix,
        JSON.stringify(keyData.permissions || []),
        JSON.stringify(rateLimit),
        keyData.expiresAt || null
      ]);

      const dbKey = result.rows[0];

      return {
        id: dbKey.id,
        name: dbKey.name,
        key: apiKey, // Only returned once during creation
        keyPrefix: dbKey.key_prefix,
        permissions: dbKey.permissions,
        rateLimit: dbKey.rate_limit,
        isActive: dbKey.is_active,
        createdAt: dbKey.created_at,
        expiresAt: dbKey.expires_at
      };
    } catch (error) {
      console.error('Create API key error:', error);
      return null;
    }
  }

  async verifyApiKey(apiKey: string): Promise<{ user: User; apiKey: ApiKey } | null> {
    try {
      // Get all active API keys and check against provided key
      const query = `
        SELECT ak.*, u.id as user_id, u.email, u.name, u.tier, u.is_active as user_active, 
               u.email_verified, u.created_at as user_created_at, u.updated_at as user_updated_at, 
               u.last_login_at
        FROM api_keys ak
        JOIN users u ON ak.user_id = u.id
        WHERE ak.is_active = true 
          AND u.is_active = true
          AND (ak.expires_at IS NULL OR ak.expires_at > NOW())
      `;

      const result = await this.db.query(query);

      for (const row of result.rows) {
        const isKeyValid = await bcrypt.compare(apiKey, row.key_hash);
        if (isKeyValid) {
          // Update last used timestamp
          await this.db.query(
            'UPDATE api_keys SET last_used_at = NOW() WHERE id = $1',
            [row.id]
          );

          const user: User = {
            id: row.user_id,
            email: row.email,
            name: row.name,
            tier: row.tier,
            isActive: row.user_active,
            emailVerified: row.email_verified,
            createdAt: row.user_created_at,
            updatedAt: row.user_updated_at,
            lastLoginAt: row.last_login_at
          };

          const apiKeyObj: ApiKey = {
            id: row.id,
            userId: row.user_id,
            name: row.name,
            keyHash: row.key_hash,
            keyPrefix: row.key_prefix,
            permissions: row.permissions,
            rateLimit: row.rate_limit,
            isActive: row.is_active,
            lastUsedAt: row.last_used_at,
            createdAt: row.created_at,
            expiresAt: row.expires_at
          };

          return { user, apiKey: apiKeyObj };
        }
      }

      return null;
    } catch (error) {
      console.error('Verify API key error:', error);
      return null;
    }
  }

  async getUserApiKeys(userId: string): Promise<Partial<ApiKey>[]> {
    try {
      const query = `
        SELECT id, name, key_prefix, permissions, rate_limit, is_active, last_used_at, created_at, expires_at
        FROM api_keys
        WHERE user_id = $1
        ORDER BY created_at DESC
      `;

      const result = await this.db.query(query, [userId]);

      return result.rows.map((row: any) => ({
        id: row.id,
        name: row.name,
        keyPrefix: row.key_prefix,
        permissions: row.permissions,
        rateLimit: row.rate_limit,
        isActive: row.is_active,
        lastUsedAt: row.last_used_at,
        createdAt: row.created_at,
        expiresAt: row.expires_at
      }));
    } catch (error) {
      console.error('Get user API keys error:', error);
      return [];
    }
  }

  async revokeApiKey(userId: string, keyId: string): Promise<boolean> {
    try {
      const query = `
        UPDATE api_keys
        SET is_active = false
        WHERE id = $1 AND user_id = $2
      `;

      const result = await this.db.query(query, [keyId, userId]);
      return (result.rowCount ?? 0) > 0;
    } catch (error) {
      console.error('Revoke API key error:', error);
      return false;
    }
  }

  // Helper Methods
  private async getUserById(userId: string): Promise<User | null> {
    try {
      const query = `
        SELECT id, email, name, tier, is_active, email_verified, created_at, updated_at, last_login_at
        FROM users
        WHERE id = $1 AND is_active = true
      `;

      const result = await this.db.query(query, [userId]);

      if (result.rows.length === 0) {
        return null;
      }

      return this.mapDbUserToUser(result.rows[0]);
    } catch (error) {
      console.error('Get user by ID error:', error);
      return null;
    }
  }

  private async getUserByEmail(email: string): Promise<User | null> {
    try {
      const query = `
        SELECT id, email, name, tier, is_active, email_verified, created_at, updated_at, last_login_at
        FROM users
        WHERE email = $1
      `;

      const result = await this.db.query(query, [email]);

      if (result.rows.length === 0) {
        return null;
      }

      return this.mapDbUserToUser(result.rows[0]);
    } catch (error) {
      console.error('Get user by email error:', error);
      return null;
    }
  }

  private async getUserSubscriptionPlan(userId: string): Promise<SubscriptionPlan | null> {
    try {
      const query = `
        SELECT sp.*
        FROM subscription_plans sp
        JOIN user_subscriptions us ON sp.id = us.plan_id
        WHERE us.user_id = $1 AND us.status = 'active'
        ORDER BY us.created_at DESC
        LIMIT 1
      `;

      const result = await this.db.query(query, [userId]);

      if (result.rows.length === 0) {
        // Return free plan as default
        const freePlanQuery = `SELECT * FROM subscription_plans WHERE tier = 'free' LIMIT 1`;
        const freePlanResult = await this.db.query(freePlanQuery);
        if (freePlanResult.rows.length > 0) {
          return this.mapDbPlanToPlan(freePlanResult.rows[0]);
        }
        return null;
      }

      return this.mapDbPlanToPlan(result.rows[0]);
    } catch (error) {
      console.error('Get user subscription plan error:', error);
      return null;
    }
  }

  private generateJWT(user: User): string {
    const payload: Omit<JWTPayload, 'iat' | 'exp'> = {
      userId: user.id,
      email: user.email,
      tier: user.tier
    };

    return jwt.sign(payload, this.config.jwtSecret, {
      expiresIn: this.config.jwtExpiresIn
    } as jwt.SignOptions);
  }

  private generateApiKey(): string {
    return crypto.randomBytes(32).toString('hex');
  }

  private mapDbUserToUser(dbUser: any): User {
    return {
      id: dbUser.id,
      email: dbUser.email,
      name: dbUser.name,
      tier: dbUser.tier,
      isActive: dbUser.is_active,
      emailVerified: dbUser.email_verified,
      createdAt: dbUser.created_at,
      updatedAt: dbUser.updated_at,
      lastLoginAt: dbUser.last_login_at
    };
  }

  private mapDbPlanToPlan(dbPlan: any): SubscriptionPlan {
    return {
      id: dbPlan.id,
      name: dbPlan.name,
      tier: dbPlan.tier,
      priceMonthly: dbPlan.price_monthly,
      priceYearly: dbPlan.price_yearly,
      rateLimit: dbPlan.rate_limits,
      features: dbPlan.features,
      isActive: dbPlan.is_active,
      createdAt: dbPlan.created_at
    };
  }
} 