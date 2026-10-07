# Nginx Configuration for OSM MCP Server

## SSL Certificates

Before running nginx in production mode, you need to generate SSL certificates.

### Option 1: Self-Signed Certificates (Development)

```bash
# Generate self-signed certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/key.pem \
  -out nginx/ssl/cert.pem \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
```

### Option 2: Let's Encrypt (Production)

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Get certificate
sudo certbot certonly --webroot -w /var/www/certbot \
  -d your-domain.com

# Copy certificates
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/key.pem
```

## Running with Nginx

```bash
# Start with nginx profile
docker-compose --profile production up -d
```

## Configuration Notes

- HTTP traffic is automatically redirected to HTTPS
- API endpoints have stricter rate limiting (10 req/s)
- Health check endpoint has no rate limiting
- Gzip compression enabled for text/JSON responses
- Security headers included

