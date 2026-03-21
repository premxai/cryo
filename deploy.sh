#!/bin/bash
# deploy.sh — One-time setup + deploy script for DigitalOcean Ubuntu 22.04 droplet.
# Run as root on the droplet: bash deploy.sh

set -euo pipefail

REPO_URL="https://github.com/premxai/cryo.git"
APP_DIR="/opt/cryo"

echo "=== Cryo Production Deploy ==="

# ── 1. System deps ─────────────────────────────────────────────────────────────
apt-get update -q
apt-get install -y -q docker.io docker-compose-v2 nginx git curl ufw
systemctl enable --now docker
systemctl enable --now nginx

# ── 2. Firewall ────────────────────────────────────────────────────────────────
ufw allow ssh
ufw allow 80/tcp
ufw --force enable
echo "Firewall configured."

# ── 3. Clone / update repo ─────────────────────────────────────────────────────
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
    echo "   Required: MEILISEARCH_KEY, POSTGRES_PASSWORD, REDIS_PASSWORD, ANTHROPIC_API_KEY"
    exit 1
fi

# ── 5. Nginx config ────────────────────────────────────────────────────────────
cp nginx/nginx.conf /etc/nginx/nginx.conf
nginx -t && systemctl reload nginx
echo "Nginx configured."

# ── 6. Start services ──────────────────────────────────────────────────────────
docker compose -f docker-compose.prod.yml pull || true
docker compose -f docker-compose.prod.yml up -d

echo ""
echo "=== Done ==="
echo "Backend health: http://$(curl -s ifconfig.me)/healthz/live"
echo "Logs: docker compose -f $APP_DIR/docker-compose.prod.yml logs -f backend"
