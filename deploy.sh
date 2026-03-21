#!/bin/bash
# deploy.sh — One-time setup + deploy script for DigitalOcean Ubuntu 22.04 droplet.
# Run as root on the droplet: bash deploy.sh
# After first run, deploys happen automatically via GitHub Actions.

set -euo pipefail

REPO_URL="https://github.com/premxai/cryo.git"
APP_DIR="/opt/cryo"

echo "=== Cryo Production Deploy ==="

# ── 1. System deps ─────────────────────────────────────────────────────────────
apt-get update -q
apt-get install -y -q docker.io docker-compose-v2 nginx certbot python3-certbot-nginx git curl ufw

# ── 2. Firewall ────────────────────────────────────────────────────────────────
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
echo "Firewall configured."

# ── 3. Clone repo ──────────────────────────────────────────────────────────────
if [ ! -d "$APP_DIR" ]; then
    git clone "$REPO_URL" "$APP_DIR"
else
    cd "$APP_DIR" && git pull
fi
cd "$APP_DIR"

# ── 4. Environment ─────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    cp .env.production .env
    echo ""
    echo "⚠️  Edit $APP_DIR/.env and fill in real values, then re-run this script."
    echo "   Required: MEILISEARCH_KEY, POSTGRES_PASSWORD, REDIS_PASSWORD, DOMAIN, GITHUB_REPO"
    exit 1
fi

# Load env vars
export $(grep -v '^#' .env | xargs)

# ── 5. SSL certificate ─────────────────────────────────────────────────────────
if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    echo "Getting SSL certificate for $DOMAIN..."
    # Temporarily serve ACME challenge on port 80
    certbot certonly --standalone -d "$DOMAIN" --non-interactive --agree-tos -m "admin@$DOMAIN"
fi

# ── 6. Nginx config ────────────────────────────────────────────────────────────
# Replace placeholders in nginx config
sed "s/\${DOMAIN}/$DOMAIN/g; s/\${FRONTEND_URL}/$FRONTEND_URL/g" \
    nginx/nginx.conf > /etc/nginx/nginx.conf
nginx -t && systemctl reload nginx

# ── 7. GitHub Container Registry login ────────────────────────────────────────
echo "Log into GitHub Container Registry:"
echo "  docker login ghcr.io -u YOURUSERNAME -p YOUR_GITHUB_PAT"
echo "(Create PAT at github.com/settings/tokens with read:packages scope)"

# ── 8. Start services ──────────────────────────────────────────────────────────
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d

echo ""
echo "=== Done ==="
echo "Backend health: https://$DOMAIN/healthz/live"
echo "Logs: docker compose -f docker-compose.prod.yml logs -f backend"
