# Cryo — $0 Demo Runbook (local stack + free public tunnel)

Run the whole product from this machine and expose it publicly only while
demoing. No paid hosting involved.

## 1. Start the stack (four services)

```powershell
# PostgreSQL + Redis (inside WSL, with keep-alive so the VM doesn't sleep)
Start-Process wsl -ArgumentList '-d','Ubuntu-24.04','-u','root','--','bash','-c','service postgresql start; service redis-server start; sleep infinity' -WindowStyle Hidden

# Meilisearch (bundled binary, data in .\data.ms)
Start-Process -FilePath ".\bin\meilisearch.exe" -ArgumentList "--master-key","cryo_dev_key","--http-addr","localhost:7700","--db-path","./data.ms","--no-analytics" -WindowStyle Hidden

# Backend API
python -m uvicorn backend.main:app --port 8010

# Frontend (optional, separate terminal)
cd frontend; npm run dev        # http://localhost:5173
```

Health check: `curl http://localhost:8010/healthz/ready` → `{"status":"ok","db":"connected"}`.

## 2. Mint a demo key

```powershell
python pipeline/issue_key.py demo@example.com
# copy the printed cryo_sk_... (shown once)
```

## 3. Expose it publicly (only while demoing)

Install cloudflared once (`winget install Cloudflare.cloudflared`), then:

```powershell
cloudflared tunnel --url http://localhost:8010
```

It prints a URL like `https://random-words.trycloudflare.com` — a public HTTPS
address for your local backend, alive until you Ctrl+C. No account needed.

## 4. The demo script (5 minutes)

```bash
TUNNEL=https://<your-tunnel>.trycloudflare.com
KEY="cryo_sk_..."

# 1) Search the frozen web — results carry authenticity scores
curl -X POST $TUNNEL/v1/search -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "do things that dont scale", "num_results": 3}'

# 2) Fetch a page NOT in the corpus — live Wayback fetch, frozen in permanently
curl -X POST $TUNNEL/v1/contents -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"urls": ["http://paulgraham.com/avg.html"], "timestamp": "20200101"}'

# 3) Search again for that essay — it's now in the index (the corpus grew)
curl -X POST $TUNNEL/v1/search -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "beating the averages lisp", "num_results": 3}'
```

The beat that lands: step 2's page was fetched live from the 2020 archive,
and step 3 proves the searchable corpus grew from a browse action.

## 5. Connect Claude to it (the flagship moment)

```bash
claude mcp add --transport http cryo https://<your-tunnel>.trycloudflare.com/mcp/ \
  --header "Authorization: Bearer cryo_sk_..."
```

Then ask Claude: *"Using cryo, find what people said about remote work before
2022 and read the most authentic-looking page in full."* Claude will chain
`cryo_search` → `cryo_get_page` live, with `human_score`/`cryo_certified` on
every result.

## Notes

- Tunnel URLs rotate per run — re-add the MCP server if you restart the tunnel.
- Closing the laptop kills the demo. That's the trade of $0; move to a paid
  host (see HETZNER_RUNBOOK.md) when someone external needs always-on access.
- Wayback live fetches take 5–20s — pre-warm step 2's URL before a live demo
  if you're nervous, or embrace the wait as proof it's real.
