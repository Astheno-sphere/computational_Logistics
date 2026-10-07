# Multi-stage build for OpenStreetMap MCP Server
FROM node:18-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./
COPY tsconfig.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY src/ ./src/

# Build the application
RUN npm run build

# Production stage
FROM node:18-alpine AS production

# Install wget for health check
RUN apk add --no-cache wget

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S mcpserver -u 1001

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install only production dependencies
RUN npm ci --only=production && npm cache clean --force

# Copy built application from builder stage
COPY --from=builder /app/dist ./dist

# Set ownership
RUN chown -R mcpserver:nodejs /app

# Switch to non-root user
USER mcpserver

# Expose ports
EXPOSE 8888 3000

# Health check using wget (more reliable than inline node script)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8888/health || exit 1

# Default command (HTTP server mode)
CMD ["node", "dist/http-server-start.js"] 