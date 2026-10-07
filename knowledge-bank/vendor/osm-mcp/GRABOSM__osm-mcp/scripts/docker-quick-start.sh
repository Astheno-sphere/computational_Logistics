#!/bin/bash

# OSM MCP Docker Quick Start Script
# This script helps you quickly deploy OSM MCP Server with Docker

set -e

COLOR_GREEN='\033[0;32m'
COLOR_BLUE='\033[0;34m'
COLOR_YELLOW='\033[1;33m'
COLOR_RESET='\033[0m'

echo -e "${COLOR_BLUE}"
cat << "EOF"
   ___  ____  __  __   __  __  ____  ____  
  / _ \/ ___||  \/  | |  \/  |/ ___||  _ \ 
 | | | \___ \| |\/| | | |\/| | |    | |_) |
 | |_| |___) | |  | | | |  | | |___ |  __/ 
  \___/|____/|_|  |_| |_|  |_|\____||_|    
                                            
  OpenStreetMap MCP Server - Docker Setup
EOF
echo -e "${COLOR_RESET}"

# Menu
echo "Select deployment mode:"
echo ""
echo "  1) Basic Mode (MCP Server only)"
echo "  2) Hosted Service (with PostgreSQL & Redis)"
echo "  3) Production Mode (with Nginx reverse proxy)"
echo "  4) Validate Configuration"
echo "  5) Stop All Services"
echo ""
read -p "Enter your choice [1-5]: " choice

case $choice in
    1)
        echo -e "${COLOR_GREEN}Starting Basic Mode...${COLOR_RESET}"
        docker-compose build
        docker-compose up -d
        echo ""
        echo -e "${COLOR_GREEN}✓ Server started!${COLOR_RESET}"
        echo "  API: http://localhost:8888"
        echo "  Health: http://localhost:8888/health"
        echo ""
        echo "Check logs: docker-compose logs -f osm-mcp"
        ;;
    2)
        echo -e "${COLOR_GREEN}Starting Hosted Service Mode...${COLOR_RESET}"
        if [ ! -f .env ]; then
            echo -e "${COLOR_YELLOW}Creating .env file...${COLOR_RESET}"
            cp env.template .env
            echo -e "${COLOR_YELLOW}⚠ Please edit .env and configure DATABASE_URL, REDIS_URL, etc.${COLOR_RESET}"
            read -p "Press Enter after editing .env..."
        fi
        docker-compose --profile hosted-service build
        docker-compose --profile hosted-service up -d
        echo ""
        echo -e "${COLOR_GREEN}✓ Services started!${COLOR_RESET}"
        echo "  API: http://localhost:8888"
        echo "  PostgreSQL: localhost:5432"
        echo "  Redis: localhost:6379"
        echo ""
        echo "Check logs: docker-compose --profile hosted-service logs -f"
        ;;
    3)
        echo -e "${COLOR_GREEN}Starting Production Mode...${COLOR_RESET}"
        
        # Check SSL certificates
        if [ ! -f nginx/ssl/cert.pem ] || [ ! -f nginx/ssl/key.pem ]; then
            echo -e "${COLOR_YELLOW}SSL certificates not found. Generating self-signed certificates...${COLOR_RESET}"
            mkdir -p nginx/ssl
            openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
                -keyout nginx/ssl/key.pem \
                -out nginx/ssl/cert.pem \
                -subj "/C=US/ST=State/L=City/O=OSM-MCP/CN=localhost"
            echo -e "${COLOR_GREEN}✓ SSL certificates generated${COLOR_RESET}"
        fi
        
        if [ ! -f .env ]; then
            echo -e "${COLOR_YELLOW}Creating .env file...${COLOR_RESET}"
            cp env.template .env
            echo -e "${COLOR_YELLOW}⚠ Please edit .env for production use${COLOR_RESET}"
            read -p "Press Enter after editing .env..."
        fi
        
        docker-compose --profile production build
        docker-compose --profile production up -d
        echo ""
        echo -e "${COLOR_GREEN}✓ Production services started!${COLOR_RESET}"
        echo "  HTTP: http://localhost:80 (redirects to HTTPS)"
        echo "  HTTPS: https://localhost:443"
        echo "  API: http://localhost:8888"
        echo ""
        echo "Check logs: docker-compose --profile production logs -f"
        ;;
    4)
        echo -e "${COLOR_GREEN}Validating configuration...${COLOR_RESET}"
        ./scripts/validate-docker.sh
        ;;
    5)
        echo -e "${COLOR_YELLOW}Stopping all services...${COLOR_RESET}"
        docker-compose --profile hosted-service --profile production down
        echo -e "${COLOR_GREEN}✓ All services stopped${COLOR_RESET}"
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

