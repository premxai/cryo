#!/bin/bash
# Nightly Postgres backup — keeps 14 days locally on the box.
# Installed via cron on the prod box: 0 3 * * * /opt/cryo/backup.sh
# TODO: once Backblaze B2 is set up, add an off-box sync step here.
set -euo pipefail
BACKUP_DIR="/opt/cryo/backups"
STAMP=$(date +%F)
FILE="$BACKUP_DIR/cryo_pg_$STAMP.sql.gz"

cd /opt/cryo
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U postgres cryo | gzip > "$FILE"
echo "[backup] $(date) wrote $FILE ($(du -h "$FILE" | cut -f1))"

# Prune anything older than 14 days
find "$BACKUP_DIR" -name "cryo_pg_*.sql.gz" -mtime +14 -delete
