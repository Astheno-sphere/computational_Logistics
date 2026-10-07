import { Request, Response, NextFunction } from 'express';
import { AuthService } from './auth-service.js';
import type { AuthRequest } from './auth-types.js';

export class AuthMiddleware {
  private authService: AuthService;

  constructor(authService: AuthService) {
    this.authService = authService;
  }

  // JWT Authentication Middleware
  authenticateJWT = async (req: AuthRequest, res: Response, next: NextFunction) => {
    try {
      const authHeader = req.headers.authorization;

      if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return res.status(401).json({
          error: 'Unauthorized',
          message: 'JWT token required'
        });
      }

      const token = authHeader.substring(7); // Remove 'Bearer ' prefix
      const user = await this.authService.verifyJWT(token);

      if (!user) {
        return res.status(401).json({
          error: 'Unauthorized',
          message: 'Invalid or expired token'
        });
      }

      req.user = user;
      next();
    } catch (error) {
      console.error('JWT authentication error:', error);
      res.status(500).json({
        error: 'Internal Server Error',
        message: 'Authentication failed'
      });
    }
  };

  // API Key Authentication Middleware
  authenticateApiKey = async (req: AuthRequest, res: Response, next: NextFunction) => {
    try {
      const apiKey = this.extractApiKey(req);

      if (!apiKey) {
        return res.status(401).json({
          error: 'Unauthorized',
          message: 'API key required'
        });
      }

      const authResult = await this.authService.verifyApiKey(apiKey);

      if (!authResult) {
        return res.status(401).json({
          error: 'Unauthorized',
          message: 'Invalid API key'
        });
      }

      req.user = authResult.user;
      req.apiKey = authResult.apiKey;
      next();
    } catch (error) {
      console.error('API key authentication error:', error);
      res.status(500).json({
        error: 'Internal Server Error',
        message: 'Authentication failed'
      });
    }
  };

  // Flexible authentication (JWT or API Key)
  authenticate = async (req: AuthRequest, res: Response, next: NextFunction) => {
    try {
      // Try API key first
      const apiKey = this.extractApiKey(req);
      if (apiKey) {
        const authResult = await this.authService.verifyApiKey(apiKey);
        if (authResult) {
          req.user = authResult.user;
          req.apiKey = authResult.apiKey;
          return next();
        }
      }

      // Try JWT token
      const authHeader = req.headers.authorization;
      if (authHeader && authHeader.startsWith('Bearer ')) {
        const token = authHeader.substring(7);
        const user = await this.authService.verifyJWT(token);
        if (user) {
          req.user = user;
          return next();
        }
      }

      // No valid authentication found
      return res.status(401).json({
        error: 'Unauthorized',
        message: 'Valid authentication required (API key or JWT token)'
      });
    } catch (error) {
      console.error('Authentication error:', error);
      res.status(500).json({
        error: 'Internal Server Error',
        message: 'Authentication failed'
      });
    }
  };

  // Optional authentication (allows both authenticated and anonymous requests)
  optionalAuth = async (req: AuthRequest, res: Response, next: NextFunction) => {
    try {
      // Try to authenticate, but don't fail if no auth provided
      const apiKey = this.extractApiKey(req);
      if (apiKey) {
        const authResult = await this.authService.verifyApiKey(apiKey);
        if (authResult) {
          req.user = authResult.user;
          req.apiKey = authResult.apiKey;
        }
      } else {
        const authHeader = req.headers.authorization;
        if (authHeader && authHeader.startsWith('Bearer ')) {
          const token = authHeader.substring(7);
          const user = await this.authService.verifyJWT(token);
          if (user) {
            req.user = user;
          }
        }
      }

      next();
    } catch (error) {
      console.error('Optional authentication error:', error);
      // Continue without authentication in case of error
      next();
    }
  };

  // Authorization middleware for different tiers
  requireTier = (requiredTier: string | string[]) => {
    return (req: AuthRequest, res: Response, next: NextFunction) => {
      if (!req.user) {
        return res.status(401).json({
          error: 'Unauthorized',
          message: 'Authentication required'
        });
      }

      const allowedTiers = Array.isArray(requiredTier) ? requiredTier : [requiredTier];
      const tierHierarchy = ['free', 'hobby', 'pro', 'enterprise'];
      
      const userTierIndex = tierHierarchy.indexOf(req.user.tier);
      const hasAccess = allowedTiers.some(tier => {
        const requiredTierIndex = tierHierarchy.indexOf(tier);
        return userTierIndex >= requiredTierIndex;
      });

      if (!hasAccess) {
        return res.status(403).json({
          error: 'Forbidden',
          message: `This feature requires ${allowedTiers.join(' or ')} tier access`
        });
      }

      next();
    };
  };

  // Permission-based authorization
  requirePermission = (permission: string) => {
    return (req: AuthRequest, res: Response, next: NextFunction) => {
      if (!req.apiKey) {
        return res.status(401).json({
          error: 'Unauthorized',
          message: 'API key required for permission check'
        });
      }

      const hasPermission = req.apiKey.permissions.includes(permission) || 
                           req.apiKey.permissions.includes('*');

      if (!hasPermission) {
        return res.status(403).json({
          error: 'Forbidden',
          message: `This action requires '${permission}' permission`
        });
      }

      next();
    };
  };

  // Development mode bypass (disable auth for local development)
  bypassAuth = (req: AuthRequest, res: Response, next: NextFunction) => {
    // Create a mock user for development
    req.user = {
      id: 'dev-user',
      email: 'dev@localhost',
      name: 'Development User',
      tier: 'enterprise',
      isActive: true,
      emailVerified: true,
      createdAt: new Date(),
      updatedAt: new Date()
    };

    next();
  };

  private extractApiKey(req: Request): string | null {
    // Check various common places for API key
    
    // 1. Authorization header with "ApiKey" or "Bearer" prefix
    const authHeader = req.headers.authorization;
    if (authHeader) {
      if (authHeader.startsWith('ApiKey ')) {
        return authHeader.substring(7);
      }
      if (authHeader.startsWith('Bearer ')) {
        const token = authHeader.substring(7);
        // Check if it looks like an API key (64 hex characters)
        if (/^[a-f0-9]{64}$/.test(token)) {
          return token;
        }
      }
    }

    // 2. X-API-Key header
    const apiKeyHeader = req.headers['x-api-key'];
    if (apiKeyHeader && typeof apiKeyHeader === 'string') {
      return apiKeyHeader;
    }

    // 3. Query parameter
    const queryApiKey = req.query.api_key || req.query.apikey;
    if (queryApiKey && typeof queryApiKey === 'string') {
      return queryApiKey;
    }

    return null;
  }
} 