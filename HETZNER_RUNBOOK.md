# Cryo — DigitalOcean → Hetzner Migration Runbook

The whole deployment is one script (`deploy.sh`) targeting a generic Ubuntu + Docker
box, so moving hosts is: salvage anything server-only → create Hetzner box → point DNS →
run the script → upload the corpus. Nothing in the stack is DO-specific.

---

## Part 1 — Before you kill the DO droplet (salvage first)

The repo is the source of truth for code, but a few things may live **only** on the
droplet. Check each before destroying it (`ssh root@<DROPLET_IP>`):

1. **The `.env` with real secrets** — the droplet's `/opt/cryo/.env` has real
   `MEILISEARCH_KEY`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `ANTHROPIC_API_KEY`,
   `SESSION_SECRET`. Copy it down:
   ```bash
   scp root@<DROPLET_IP>:/opt/cryo/.env ./droplet.env.backup
   ```
2. **Any corpus indexed only on the droplet.** If you ran ingest/download there, the
   JSONL under `/opt/cryo/data/raw/` may be larger than your local `data/raw/`. Pull it:
   ```bash
   scp -r root@<DROPLET_IP>:/opt/cryo/data/raw ./droplet_data_raw
   ```
   (The Meilisearch/Postgres **volumes** don't need saving — they're rebuilt from JSONL.)
3. **Registered users / API keys / usage** in the droplet's Postgres, if any real users
   exist. Dump it:
   ```bash
   ssh root@<DROPLET_IP> "docker compose -f /opt/cryo/docker-compose.prod.yml exec -T postgres pg_dump -U postgres cryo" > cryo_pg_backup.sql
   ```

**Then kill the droplet** from the DigitalOcean dashboard (Droplets → … → Destroy) or
`doctl compute droplet delete <id>`. *(This can't be done from the repo — it needs your
DO account. Billing stops when the droplet is destroyed, not just powered off.)*

---

## Part 2 — Create the Hetzner box

- **Hetzner Cloud console** → new project → new server.
- Location: Nuremberg/Falkenstein (EU) or Ashburn (US) — closest to your users.
- Image: **Ubuntu 24.04**.
- Type: **CX22** (2 vCPU / 4 GB / 40 GB, ~€4.50/mo) for the current ~1.2k–250k corpus.
  Step up to **CX32** (4 vCPU / 8 GB / 80 GB, ~€8/mo) only when you load the 1M-doc corpus.
- Add your SSH key during creation.
- After boot, note the IPv4. (Optional: `ufw` is configured by `deploy.sh`.)

---

## Part 3 — DNS

Point your domain at the new box (skip if you'll demo by raw IP first):
- `A  api.yourdomain.com  →  <HETZNER_IP>`
- `A  yourdomain.com      →  <HETZNER_IP>`  (or Vercel, if you host the frontend there)

---

## Part 4 — Deploy

```bash
ssh root@<HETZNER_IP>

# deploy.sh clones the repo to /opt/cryo, installs docker+nginx, configures firewall.
# It errors out the first time asking you to fill in .env — that's expected.
curl -fsSL https://raw.githubusercontent.com/premxai/cryo/main/deploy.sh -o deploy.sh
bash deploy.sh              # first run: sets up, then stops for .env

# Restore the salvaged secrets (or hand-edit /opt/cryo/.env from .env.production template)
scp ./droplet.env.backup root@<HETZNER_IP>:/opt/cryo/.env
#   IMPORTANT: set a fresh strong SESSION_SECRET and PUBLIC_BASE_URL=https://yourdomain.com

bash deploy.sh              # second run: alembic upgrade head → starts all services
```

`deploy.sh` already runs `alembic upgrade head` before bringing the backend up, and
attempts the one-time `load_documents_pg.py` corpus load.

---

## Part 5 — Upload the corpus (the data isn't in git)

`data/raw/*.jsonl` is gitignored, so `git clone` doesn't bring it. Upload it (only ~4.6 MB
locally, or use the `droplet_data_raw` you salvaged):

```bash
scp -r ./data/raw/* root@<HETZNER_IP>:/opt/cryo/data/raw/

# Index into Meilisearch + load into Postgres (inside the backend container)
ssh root@<HETZNER_IP> "cd /opt/cryo && \
  docker compose -f docker-compose.prod.yml exec -T backend python pipeline/index.py && \
  docker compose -f docker-compose.prod.yml exec -T backend python pipeline/load_documents_pg.py"
```

If you saved a `cryo_pg_backup.sql` with real users, restore it instead of/after the
fresh load:
```bash
cat cryo_pg_backup.sql | ssh root@<HETZNER_IP> \
  "docker compose -f /opt/cryo/docker-compose.prod.yml exec -T postgres psql -U postgres cryo"
```

---

## Part 6 — Verify (same checks that passed locally)

```bash
# Health
curl http://<HETZNER_IP>/healthz/ready         # {"status":"ok","db":"connected"}

# Mint a key, then exercise the API
ssh root@<HETZNER_IP> "cd /opt/cryo && docker compose -f docker-compose.prod.yml exec -T backend python pipeline/issue_key.py you@example.com"

curl -X POST http://<HETZNER_IP>/v1/search \
  -H "Authorization: Bearer cryo_sk_..." -H "Content-Type: application/json" \
  -d '{"query":"internet history","num_results":3}'

# MCP handshake
curl -X POST http://<HETZNER_IP>/mcp/ \
  -H "Authorization: Bearer cryo_sk_..." \
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

Then add TLS: point Cloudflare (free) at the box, or run certbot for Let's Encrypt on nginx.

---

## Backups (make the box disposable)

Nightly `pg_dump` + the JSONL corpus are all you need to rebuild anywhere:
```bash
# cron on the box, or from your laptop
docker compose -f /opt/cryo/docker-compose.prod.yml exec -T postgres \
  pg_dump -U postgres cryo | gzip > cryo_$(date +%F).sql.gz
```
Store off-box (Backblaze B2 free 10 GB, or just your laptop). With that + the repo, any
future host is one `deploy.sh` away.

---

## Cost summary

| Host | Spec | Corpus it fits | ~Monthly |
|---|---|---|---|
| Hetzner CX22 | 2c / 4 GB / 40 GB | current → ~250k docs | €4.50 (~$5) |
| Hetzner CX32 | 4c / 8 GB / 80 GB | ~1M docs | €8 (~$8.50) |
| + Backblaze B2 backups | 10 GB | — | $0 |
