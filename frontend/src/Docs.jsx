const API_URL = import.meta.env.VITE_API_URL || window.location.origin

/**
 * Code block with a muted label.
 */
function Code({ label, children }) {
  return (
    <div className="mb-6">
      <div className="text-xs text-white/40 mb-1.5 tracking-wide">{label}</div>
      <pre className="liquid-glass rounded-xl p-4 text-xs text-white/80 overflow-x-auto whitespace-pre leading-relaxed">
        {children}
      </pre>
    </div>
  )
}

/**
 * Docs — quickstart for the /v1 REST API and the hosted MCP server.
 */
export default function Docs() {
  return (
    <div className="w-full max-w-3xl pb-16">
      <h1 className="gradient-heading text-3xl mb-2">API Documentation</h1>
      <p className="text-sm text-white/50 mb-10 font-light">
        Search and browse the frozen pre-2022 human web. Get a key from the{' '}
        <a href="#/dashboard" className="text-white/80 underline underline-offset-2">dashboard</a>,
        then authenticate every request with <code className="text-white/70">Authorization: Bearer cryo_sk_...</code>
      </p>

      <h2 className="text-lg text-white/90 mb-4">Search</h2>
      <Code label="POST /v1/search">
{`curl -X POST ${API_URL}/v1/search \\
  -H "Authorization: Bearer cryo_sk_YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"query": "how to start a startup", "num_results": 10}'`}
      </Code>

      <h2 className="text-lg text-white/90 mb-4">Read full pages (the browse loop)</h2>
      <p className="text-sm text-white/50 mb-4 font-light">
        Fetch full text by result id or any URL — pages not yet in the corpus are pulled live
        from the Wayback Machine (always pre-2022 snapshots) and frozen in. Live fetches
        return outbound links your agent can follow.
      </p>
      <Code label="POST /v1/contents">
{`curl -X POST ${API_URL}/v1/contents \\
  -H "Authorization: Bearer cryo_sk_YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"urls": ["http://paulgraham.com/ds.html"], "timestamp": "20200101"}'`}
      </Code>

      <h2 className="text-lg text-white/90 mb-4">Find similar</h2>
      <Code label="POST /v1/find-similar">
{`curl -X POST ${API_URL}/v1/find-similar \\
  -H "Authorization: Bearer cryo_sk_YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"id": "SOURCE_DOC_ID", "num_results": 10}'`}
      </Code>

      <h2 className="text-lg text-white/90 mb-4">Python</h2>
      <Code label="httpx">
{`import httpx

API = "${API_URL}"
HEADERS = {"Authorization": "Bearer cryo_sk_YOUR_KEY"}

r = httpx.post(f"{API}/v1/search", headers=HEADERS,
               json={"query": "geocities culture", "num_results": 5})
for hit in r.json()["results"]:
    page = httpx.post(f"{API}/v1/contents", headers=HEADERS,
                      json={"ids": [hit["id"]]}).json()
    print(hit["url"], len(page["results"][0]["text"]))`}
      </Code>

      <h2 className="text-lg text-white/90 mb-4">MCP — use Cryo from Claude</h2>
      <p className="text-sm text-white/50 mb-4 font-light">
        A hosted MCP server exposes <code className="text-white/70">cryo_search</code>,{' '}
        <code className="text-white/70">cryo_get_page</code> and{' '}
        <code className="text-white/70">cryo_find_similar</code> as native agent tools.
      </p>
      <Code label="Claude Code">
{`claude mcp add --transport http cryo ${API_URL}/mcp/ \\
  --header "Authorization: Bearer cryo_sk_YOUR_KEY"`}
      </Code>
      <Code label="MCP client config (JSON)">
{`{
  "mcpServers": {
    "cryo": {
      "type": "http",
      "url": "${API_URL}/mcp/",
      "headers": { "Authorization": "Bearer cryo_sk_YOUR_KEY" }
    }
  }
}`}
      </Code>

      <h2 className="text-lg text-white/90 mb-4">Limits & errors</h2>
      <div className="text-sm text-white/50 font-light space-y-2 mb-6">
        <p>Free tier: 1,000 requests/month, 60 requests/minute per key. Each /v1/contents item counts as one request.</p>
        <p>Responses carry <code className="text-white/70">X-RateLimit-Remaining</code> and{' '}
        <code className="text-white/70">X-Quota-Remaining</code> headers; check{' '}
        <code className="text-white/70">GET /v1/usage</code> for a monthly breakdown.</p>
        <p>Errors are always{' '}
        <code className="text-white/70">{'{"error": {"type", "message", "request_id"}}'}</code>{' '}
        — types include <code className="text-white/70">rate_limited</code> (with Retry-After) and{' '}
        <code className="text-white/70">quota_exceeded</code>.</p>
      </div>
    </div>
  )
}
