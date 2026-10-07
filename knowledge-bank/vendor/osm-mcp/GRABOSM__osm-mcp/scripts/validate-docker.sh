#!/bin/bash

# OSM MCP Docker Configuration Validator
# This script validates Docker configuration files and required directories

set -e

COLOR_RED='\033[0;31m'
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[1;33m'
COLOR_BLUE='\033[0;34m'
COLOR_RESET='\033[0m'

echo -e "${COLOR_BLUE}╔════════════════════════════════════════════════╗${COLOR_RESET}"
echo -e "${COLOR_BLUE}║  OSM MCP Docker Configuration Validator       ║${COLOR_RESET}"
echo -e "${COLOR_BLUE}╚════════════════════════════════════════════════╝${COLOR_RESET}"
echo ""

ERRORS=0
WARNINGS=0

# Function to print status
print_status() {
    local status=$1
    local message=$2
    if [ "$status" = "OK" ]; then
        echo -e "${COLOR_GREEN}✓${COLOR_RESET} $message"
    elif [ "$status" = "WARN" ]; then
        echo -e "${COLOR_YELLOW}⚠${COLOR_RESET} $message"
        ((WARNINGS++))
    else
        echo -e "${COLOR_RED}✗${COLOR_RESET} $message"
        ((ERRORS++))
    fi
}

# Check if files exist
echo -e "${COLOR_BLUE}Checking required files...${COLOR_RESET}"

if [ -f "Dockerfile" ]; then
    print_status "OK" "Dockerfile found"
else
    print_status "ERROR" "Dockerfile not found"
fi

if [ -f "docker-compose.yml" ]; then
    print_status "OK" "docker-compose.yml found"
else
    print_status "ERROR" "docker-compose.yml not found"
fi

if [ -f ".dockerignore" ]; then
    print_status "OK" ".dockerignore found"
else
    print_status "WARN" ".dockerignore not found (recommended)"
fi

if [ -f "env.template" ]; then
    print_status "OK" "env.template found"
else
    print_status "WARN" "env.template not found"
fi

echo ""

# Check directories
echo -e "${COLOR_BLUE}Checking required directories...${COLOR_RESET}"

if [ -d "scripts" ]; then
    print_status "OK" "scripts/ directory exists"
    if [ -f "scripts/init-db.sql" ]; then
        print_status "OK" "scripts/init-db.sql exists"
    else
        print_status "ERROR" "scripts/init-db.sql not found"
    fi
else
    print_status "ERROR" "scripts/ directory not found"
fi

if [ -d "nginx" ]; then
    print_status "OK" "nginx/ directory exists"
    if [ -f "nginx/nginx.conf" ]; then
        print_status "OK" "nginx/nginx.conf exists"
    else
        print_status "ERROR" "nginx/nginx.conf not found"
    fi
    if [ -d "nginx/ssl" ]; then
        print_status "OK" "nginx/ssl/ directory exists"
        if [ -f "nginx/ssl/cert.pem" ] && [ -f "nginx/ssl/key.pem" ]; then
            print_status "OK" "SSL certificates found"
        else
            print_status "WARN" "SSL certificates not found (required for production profile)"
        fi
    else
        print_status "WARN" "nginx/ssl/ directory not found"
    fi
else
    print_status "WARN" "nginx/ directory not found (required for production profile)"
fi

if [ -d "src" ]; then
    print_status "OK" "src/ directory exists"
else
    print_status "ERROR" "src/ directory not found"
fi

if [ -d "dist" ]; then
    print_status "OK" "dist/ directory exists (built)"
else
    print_status "WARN" "dist/ directory not found (run 'npm run build')"
fi

echo ""

# Validate docker-compose.yml syntax
echo -e "${COLOR_BLUE}Validating docker-compose.yml syntax...${COLOR_RESET}"

if command -v docker-compose &> /dev/null; then
    if docker-compose config > /dev/null 2>&1; then
        print_status "OK" "docker-compose.yml syntax is valid"
    else
        print_status "ERROR" "docker-compose.yml has syntax errors"
        docker-compose config
    fi
else
    print_status "WARN" "docker-compose not installed, skipping syntax check"
fi

echo ""

# Check Dockerfile best practices
echo -e "${COLOR_BLUE}Checking Dockerfile best practices...${COLOR_RESET}"

if grep -q "FROM.*alpine" Dockerfile; then
    print_status "OK" "Using Alpine-based image (small footprint)"
fi

if grep -q "HEALTHCHECK" Dockerfile; then
    print_status "OK" "Health check configured"
fi

if grep -q "USER" Dockerfile; then
    print_status "OK" "Running as non-root user"
fi

if grep -q "COPY package.*json" Dockerfile; then
    print_status "OK" "Using layer caching for dependencies"
fi

echo ""

# Check environment variables
echo -e "${COLOR_BLUE}Checking environment configuration...${COLOR_RESET}"

if [ -f ".env" ]; then
    print_status "OK" ".env file exists"
    
    # Check for sensitive defaults
    if grep -q "JWT_SECRET=.*secret" .env 2>/dev/null; then
        print_status "WARN" "JWT_SECRET contains 'secret' - use a strong random value"
    fi
    
    if grep -q "POSTGRES_PASSWORD=.*pass" .env 2>/dev/null; then
        print_status "WARN" "POSTGRES_PASSWORD contains 'pass' - change default password"
    fi
    
    if grep -q "REDIS_PASSWORD=.*pass" .env 2>/dev/null; then
        print_status "WARN" "REDIS_PASSWORD contains 'pass' - change default password"
    fi
else
    print_status "WARN" ".env file not found (will use defaults from docker-compose.yml)"
fi

echo ""

# Summary
echo -e "${COLOR_BLUE}═════════════════════════════════════════════════${COLOR_RESET}"
echo -e "${COLOR_BLUE}Summary:${COLOR_RESET}"

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${COLOR_GREEN}✓ All checks passed!${COLOR_RESET}"
    echo -e "${COLOR_GREEN}  Your Docker configuration is ready.${COLOR_RESET}"
elif [ $ERRORS -eq 0 ]; then
    echo -e "${COLOR_YELLOW}⚠ $WARNINGS warning(s) found${COLOR_RESET}"
    echo -e "${COLOR_YELLOW}  Review warnings above. Configuration should work.${COLOR_RESET}"
else
    echo -e "${COLOR_RED}✗ $ERRORS error(s) and $WARNINGS warning(s) found${COLOR_RESET}"
    echo -e "${COLOR_RED}  Fix errors before deploying.${COLOR_RESET}"
    exit 1
fi

echo ""
echo -e "${COLOR_BLUE}Next steps:${COLOR_RESET}"
echo "  1. Build: docker-compose build"
echo "  2. Start: docker-compose up -d"
echo "  3. Check: curl http://localhost:8888/health"
echo ""
echo "For production deployment, see DOCKER.md"

