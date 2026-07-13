import { useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'https://api.cryoweb.xyz'

const SNIPPETS = {
  curl: {
    caption: 'Search with your API key.',
    code: `curl -X POST ${API_URL}/v1/search \\
  -H "Authorization: Bearer cryo_sk_YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"query": "coastal cities", "num_results": 10}'`,
  },
  python: {
    caption: 'Use the typed SDK for the same query.',
    code: `# pip install cryo-search
from cryo_search import CryoClient

cryo = CryoClient(api_key="cryo_sk_YOUR_KEY")

results = cryo.search("coastal cities", num_results=5)
page = cryo.contents(ids=[results[0].id])
answer = cryo.answer("what was the early web like?")
for c in answer.citations:
    print(c.index, c.url, c.timestamp[:8])`,
  },
  agent: {
    caption: 'Drop ledger-aware tools into any LangChain / LangGraph agent.',
    code: `# pip install "cryo-search[langchain]"
from cryo_search.langchain import CryoSearchTool, CryoAnswerTool

tools = [
    CryoSearchTool(api_key="cryo_sk_YOUR_KEY"),
    CryoAnswerTool(api_key="cryo_sk_YOUR_KEY"),
]`,
  },
  mcp: {
    caption: 'Add CRYO to Claude Code or another MCP client.',
    code: `claude mcp add --transport http cryo ${API_URL}/mcp/ \\
  --header "Authorization: Bearer cryo_sk_YOUR_KEY"

# or, MCP client config:
{
  "mcpServers": {
    "cryo": {
      "type": "http",
      "url": "${API_URL}/mcp/",
      "headers": { "Authorization": "Bearer cryo_sk_YOUR_KEY" }
    }
  }
}`,
  },
}

const TABS = [
  { key: 'curl', label: 'cURL' },
  { key: 'python', label: 'Python' },
  { key: 'agent', label: 'Agent tool' },
  { key: 'mcp', label: 'MCP' },
]

const ENDPOINTS = [
  { method: 'POST /v1/search', desc: 'Query the frozen corpus with filters and a returned source ledger.', cost: '1 UNIT' },
  { method: 'POST /v1/contents', desc: "Retrieve a source's full text and archive metadata (live Wayback fallback).", cost: '1 UNIT' },
  { method: 'POST /v1/find-similar', desc: 'Find adjacent material from a known corpus document.', cost: '3 UNITS' },
  { method: 'POST /v1/answer', desc: 'Grounded synthesis, citations required, error state if unavailable.', cost: '3 UNITS' },
  { method: 'POST /v1/list-domain', desc: "Inspect the available capture set for a domain.", cost: '1 UNIT' },
  { method: 'GET /v1/usage', desc: 'Read current-period endpoint usage and reset time.', cost: '0 UNITS' },
]

/**
 * Docs — one source-ledger contract across REST, SDK, and MCP.
 */
export default function Docs() {
  const [tab, setTab] = useState('curl')
  const [copyLabel, setCopyLabel] = useState('Copy snippet')

  async function copy() {
    try {
      await navigator.clipboard.writeText(SNIPPETS[tab].code)
      setCopyLabel('Copied')
    } catch {
      setCopyLabel('Copy failed — select text')
    }
    setTimeout(() => setCopyLabel('Copy snippet'), 1800)
  }

  return (
    <>
      <section className="page-intro docs-intro">
        <p className="eyebrow"><span></span> DEVELOPER REFERENCE / V1</p>
        <h1>Build on a web<br />you can <em>inspect.</em></h1>
        <p>One source-ledger contract across REST, SDK, and MCP. Pick the interface; keep the context.</p>
      </section>

      <section className="quickstart">
        <aside>
          <p>START HERE</p>
          <a href="#endpoints">Endpoints</a>
          <a href="#mcp">MCP server</a>
          <a href="#errors">Error model</a>
          <a href="#/dashboard">Get a key</a>
          <p className="side-note">
            Every response includes source URLs, capture dates, and an authenticity state. An
            absent score is rendered as <b>unscored</b>, never as a score.
          </p>
        </aside>
        <div className="code-area">
          <div className="code-head">
            <p>FIRST REQUEST</p>
            <div className="code-tabs" role="tablist" aria-label="Quickstart language">
              {TABS.map((t) => (
                <button
                  key={t.key}
                  className={`code-tab${tab === t.key ? ' is-active' : ''}`}
                  role="tab"
                  aria-selected={tab === t.key}
                  onClick={() => setTab(t.key)}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
          <pre><code>{SNIPPETS[tab].code}</code></pre>
          <div className="code-foot">
            <span>{SNIPPETS[tab].caption}</span>
            <button type="button" className="copy-button" onClick={copy}>{copyLabel}</button>
          </div>
        </div>
      </section>

      <section className="endpoint-section" id="endpoints">
        <p className="eyebrow"><span></span> ENDPOINTS / QUOTA IS EXPLICIT</p>
        <h2>Small surface.<br /><em>Clear contracts.</em></h2>
        <div className="endpoint-list">
          {ENDPOINTS.map((e) => (
            <article key={e.method}>
              <code>{e.method}</code>
              <p>{e.desc}</p>
              <span>{e.cost}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="docs-two-up">
        <article id="mcp">
          <p className="eyebrow"><span></span> MCP SERVER</p>
          <h2>Give an agent<br />a ledger.</h2>
          <p>
            Connect CRYO with five visible tools: <code>cryo_search</code>,{' '}
            <code>cryo_get_page</code>, <code>cryo_find_similar</code>,{' '}
            <code>cryo_list_domain</code>, and <code>cryo_answer</code>.
          </p>
          <pre className="mini-code"><code>{`claude mcp add --transport http cryo \\
  ${API_URL}/mcp/ \\
  --header "Authorization: Bearer cryo_sk_..."`}</code></pre>
          <a href="#/dashboard">Create a key <span aria-hidden="true">→</span></a>
        </article>
        <article id="errors">
          <p className="eyebrow"><span></span> ERROR MODEL</p>
          <h2>Failures should<br />be <em>useful.</em></h2>
          <dl>
            <div><dt>401</dt><dd>Missing or invalid key. Create or replace it.</dd></div>
            <div><dt>429</dt><dd>Rate limit hit. Retry after the returned interval.</dd></div>
            <div><dt>402 / 403</dt><dd>Quota exhausted. Show reset date and pricing.</dd></div>
            <div><dt>503</dt><dd>Answer service unavailable. Never fabricate a response.</dd></div>
          </dl>
        </article>
      </section>

      <section className="method-note" id="method">
        <p className="eyebrow"><span></span> METHODOLOGY</p>
        <h2>Marketing stops<br />where the data <em>does.</em></h2>
        <p>
          Documentation publishes corpus provenance, judge configuration, and the current share
          of scored versus pending documents. The interface surfaces <b>unscored</b> wherever a
          score does not exist.
        </p>
        <a href="#/pricing">See quota policy <span aria-hidden="true">→</span></a>
      </section>
    </>
  )
}
