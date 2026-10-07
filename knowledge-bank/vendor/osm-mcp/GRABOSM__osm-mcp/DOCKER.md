# Docker Deployment Guide

## Overview

This project includes Docker and Docker Compose configurations for easy deployment of the OSM MCP Server.

## Quick Start

### Basic Deployment (MCP Server Only)

```bash
# Build and start the server
docker-compose up -d

# View logs
docker-compose logs -f osm-mcp

# Stop the server
docker-compose down
```

The server will be available at:
- HTTP API: http://localhost:8888
- Health Check: http://localhost:8888/health

### Hosted Service Mode (with PostgreSQL & Redis)

```bash
# Copy environment template
cp env.template .env

# Edit .env and configure DATABASE_URL, REDIS_URL, JWT_SECRET, etc.

# Start with hosted-service profile
docker-compose --profile hosted-service up -d

# Check all services
docker-compose --profile hosted-service ps
```

### Production Mode (with Nginx)

```bash
# Generate SSL certificates first (see nginx/README.md)
cd nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout key.pem -out cert.pem \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
cd ../..

# Start with production profile
docker-compose --profile production up -d
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Docker Network                       │
│                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────┐  │
│  │    Nginx     │───▶│  OSM MCP     │───▶│PostgreSQL│  │
│  │  (optional)  │    │   Server     │    │(optional)│  │
│  └──────────────┘    └──────────────┘    └──────────┘  │
│                             │                           │
│                             ▼                           │
│                      ┌──────────────┐                   │
│                      │    Redis     │                   │
│                      │  (optional)  │                   │
│                      └──────────────┘                   │
└─────────────────────────────────────────────────────────┘
```

## Services

### 1. osm-mcp (Main Service)
- **Image**: Built from Dockerfile
- **Ports**: 8888 (API), 3000 (WebApp)
- **Always runs**: Yes
- **Purpose**: Main MCP server with OSM integration

### 2. postgres (Optional)
- **Image**: postgres:15-alpine
- **Port**: 5432
- **Profile**: `hosted-service`
- **Purpose**: Database for user authentication and rate limiting

### 3. redis (Optional)
- **Image**: redis:7-alpine
- **Port**: 6379
- **Profile**: `hosted-service`
- **Purpose**: Caching and distributed rate limiting

### 4. nginx (Optional)
- **Image**: nginx:alpine
- **Ports**: 80 (HTTP), 443 (HTTPS)
- **Profile**: `production`
- **Purpose**: Reverse proxy, SSL termination, rate limiting

## Configuration

### Environment Variables

Create a `.env` file based on `env.template`:

```bash
# Server Configuration
NODE_ENV=production
PORT=8888
LOG_LEVEL=info

# Authentication (for hosted service)
ENABLE_AUTH=false
JWT_SECRET=your-super-secret-jwt-key-change-this

# Database (for hosted service)
DATABASE_URL=postgresql://osmuser:osmpass@postgres:5432/osmmcp
POSTGRES_DB=osmmcp
POSTGRES_USER=osmuser
POSTGRES_PASSWORD=osmpass

# Redis (for hosted service)
REDIS_URL=redis://:redispass@redis:6379
REDIS_PASSWORD=redispass

# Rate Limiting
RATE_LIMIT_ENABLED=false

# CORS
CORS_ORIGIN=*
```

### Docker Compose Profiles

- **Default** (no profile): Runs only osm-mcp server
- **hosted-service**: Adds PostgreSQL, Redis, and admin dashboard
- **production**: Adds Nginx reverse proxy

## Volume Management

### Data Persistence

```bash
# List volumes
docker volume ls

# Backup PostgreSQL data
docker exec osm-mcp-postgres pg_dump -U osmuser osmmcp > backup.sql

# Restore PostgreSQL data
cat backup.sql | docker exec -i osm-mcp-postgres psql -U osmuser -d osmmcp

# Backup Redis data
docker exec osm-mcp-redis redis-cli --rdb /data/dump.rdb

# Clean up volumes
docker-compose down -v
```

## Troubleshooting

### Check Service Health

```bash
# Check all services
docker-compose ps

# Check logs
docker-compose logs -f osm-mcp
docker-compose logs -f postgres
docker-compose logs -f redis

# Check health endpoint
curl http://localhost:8888/health
```

### Common Issues

#### Issue: "Cannot connect to database"
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres

# Verify connection
docker exec osm-mcp-postgres psql -U osmuser -d osmmcp -c "SELECT 1"
```

#### Issue: "Port already in use"
```bash
# Change port in .env
PORT=9999

# Or find and kill process using port
lsof -ti:8888 | xargs kill -9
```

#### Issue: "Health check failing"
```bash
# Check if wget is installed in container
docker exec osm-mcp-server wget --version

# Check if server is actually running
docker exec osm-mcp-server ps aux | grep node

# Check server logs
docker logs osm-mcp-server
```

## Building

### Build from Scratch

```bash
# Build without cache
docker-compose build --no-cache

# Build specific service
docker-compose build osm-mcp
```

### Multi-Architecture Build

```bash
# Build for multiple platforms
docker buildx build --platform linux/amd64,linux/arm64 -t osm-mcp:latest .
```

## Development

### Development Mode with Hot Reload

For development, it's better to run outside Docker:

```bash
npm run dev        # MCP mode
npm run dev:http   # HTTP server mode
```

### Testing Docker Build Locally

```bash
# Build the image
docker build -t osm-mcp-test .

# Run container
docker run -p 8888:8888 -e NODE_ENV=development osm-mcp-test

# Test health endpoint
curl http://localhost:8888/health
```

## Production Deployment

### Pre-Deployment Checklist

- [ ] SSL certificates generated and placed in `nginx/ssl/`
- [ ] `.env` file configured with secure secrets
- [ ] `JWT_SECRET` set to a strong random value
- [ ] Database credentials changed from defaults
- [ ] Redis password set
- [ ] `CORS_ORIGIN` restricted to your domain
- [ ] Firewall rules configured
- [ ] Backup strategy in place

### Deploy to Production

```bash
# Pull latest code
git pull origin main

# Stop existing containers
docker-compose --profile production down

# Rebuild images
docker-compose --profile production build

# Start services
docker-compose --profile production up -d

# Verify deployment
docker-compose --profile production ps
curl https://your-domain.com/health
```

### Update Procedure

```bash
# Zero-downtime update
docker-compose --profile production pull
docker-compose --profile production up -d --no-deps --build osm-mcp

# Or with brief downtime
docker-compose --profile production down
docker-compose --profile production up -d --build
```

## Security Best Practices

1. **Change default passwords** in `.env`
2. **Use SSL certificates** from Let's Encrypt or a trusted CA
3. **Restrict CORS_ORIGIN** to your domain
4. **Enable authentication** with `ENABLE_AUTH=true`
5. **Use strong JWT_SECRET** (min 32 random characters)
6. **Keep images updated**: `docker-compose pull && docker-compose up -d`
7. **Limit exposed ports** using firewall rules
8. **Monitor logs** regularly for suspicious activity

## Monitoring

### Health Checks

```bash
# Check service health
curl http://localhost:8888/health

# Monitor with watch
watch -n 5 'curl -s http://localhost:8888/health | jq'
```

### Resource Usage

```bash
# Check container stats
docker stats osm-mcp-server

# Check disk usage
docker system df

# Clean up unused images
docker system prune -a
```

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/documentation)

