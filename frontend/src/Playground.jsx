import { useEffect, useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL || ''

const EXAMPLES = [
  'How did cities plan for coastal sea level rise before 2022?',
  'What did people think about remote work before 2022?',
  'What was the culture of the early web like?',
]

/** Read a ?q= deep-link out of the hash (e.g. #/ask?q=...). */
function readHashQuery() {
  const hash = window.location.hash.replace(/^#\/?/, '')
  const [, query] = hash.split('?')
  return new URLSearchParams(query || '').get('q') || ''
}

/** Render answer text with [n] citation markers as superscript anchors. */
function AnswerText({ text }) {
  const parts = text.split(/(\[\d+\])/g)
  return (
    <p>
      {parts.map((part, i) => {
        const m = part.match(/^\[(\d+)\]$/)
        if (!m) return <span key={i}>{part}</span>
        return <sup key={i}><a href={`#cite-${m[1]}`}>[{m[1]}]</a></sup>
      })}
    </p>
  )
}

function formatCapture(ts) {
  return ts && ts.length >= 8
    ? `${ts.slice(0, 4)}-${ts.slice(4, 6)}-${ts.slice(6, 8)}`
    : ''
}

/**
 * Playground — "ask the pre-AI web": live /v1/answer demo via the rate-limited
 * server-side proxy (no API key in the browser).
 */
export default function Playground() {
  const [query, setQuery] = useState(() => readHashQuery() || EXAMPLES[0])
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [status, setStatus] = useState('READY / GROUNDED ONLY')

  // Auto-run if arriving via a ?q= deep link.
  useEffect(() => {
    const q = readHashQuery()
    if (q) ask(q)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function ask(q) {
    const question = (q ?? query).trim()
    if (question.length < 3 || loading) return
    setQuery(question)
    setLoading(true)
    setError(null)
    setResult(null)
    setStatus('READING THE FROZEN ARCHIVE…')
    try {
      const r = await fetch(`${API_URL}/demo/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: question }),
      })
      const data = await r.json()
      if (!r.ok) throw new Error(data?.error?.message || `Request failed (${r.status})`)
      setResult(data)
      setStatus('COMPLETE / GROUNDED')
    } catch (err) {
      setError(err.message)
      setStatus('UNAVAILABLE')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <section className="page-intro">
        <p className="eyebrow"><span></span> /V1/ANSWER / GROUNDED ONLY</p>
        <h1>Ask the web<br />before it <em>changed.</em></h1>
        <p>
          Answers are assembled only from frozen pre-2022 sources — every citation is an
          archived snapshot with an authenticity state. Nothing here can be AI-contaminated,
          by construction.
        </p>
      </section>

      <section className="ask-console">
        <form onSubmit={(e) => { e.preventDefault(); ask() }}>
          <label htmlFor="ask-question">Question</label>
          <textarea
            id="ask-question"
            rows="3"
            maxLength={500}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div>
            <span>Live answer via the rate-limited demo proxy · no key required</span>
            <button className="ink-button" type="submit" disabled={loading}>
              {loading ? 'Thinking…' : <>Ask CRYO <span aria-hidden="true">→</span></>}
            </button>
          </div>
        </form>
        <aside>
          <p>ANSWER RULE</p>
          <strong>0</strong>
          <span>unlinked claims allowed</span>
          <p>MAXIMUM</p>
          <strong>08</strong>
          <span>sources per response</span>
        </aside>
      </section>

      <section className="answer-surface" aria-live="polite">
        <div className="answer-head">
          <span>{status}</span>
          <span>{result ? `${String(result.citations.length).padStart(2, '0')} SOURCES` : '— SOURCES'}</span>
        </div>

        <div className="answer-content">
          {error && <p style={{ color: 'var(--copper)' }}>{error}</p>}
          {!error && !result && !loading && (
            <p className="answer-placeholder">
              Ask a question to generate a grounded answer. Every claim links to a frozen
              source, or CRYO returns an honest unavailable state.
            </p>
          )}
          {!error && !result && loading && (
            <p className="answer-placeholder">Reading the frozen archive…</p>
          )}
          {result && (
            <>
              <AnswerText text={result.answer} />
              <p className="answer-meta">
                {result.cached ? 'CACHED · ' : ''}MODEL: {result.model}
              </p>
            </>
          )}
        </div>

        {result && (
          <ol className="citation-list">
            {result.citations.map((c) => (
              <li key={c.index} id={`cite-${c.index}`}>
                <b>
                  {String(c.index).padStart(2, '0')} /{' '}
                  {c.human_score != null ? `HUMAN ${c.human_score.toFixed(2)}` : 'UNSCORED'}
                </b>
                <a href={c.archive_url || c.url} target="_blank" rel="noreferrer">{c.url}</a>
                <span>
                  Captured {formatCapture(c.timestamp)}<br />
                  {c.archive_url ? 'Archive snapshot available' : 'Live source'}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>

      {!result && !loading && (
        <section className="method-note" style={{ borderBottom: 'none', paddingBottom: '2rem' }}>
          <p className="eyebrow"><span></span> TRY ONE</p>
          <div className="filter-group" style={{ gridColumn: 'span 2' }}>
            {EXAMPLES.map((ex) => (
              <button key={ex} type="button" className="filter" onClick={() => ask(ex)}>
                {ex}
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="method-note">
        <p className="eyebrow"><span></span> WHY THIS MATTERS</p>
        <h2>A citation is not<br />a <em>decoration.</em></h2>
        <p>
          Each citation exposes the live source, its archived copy, capture timestamp, and
          authenticity state. If no relevant source exists, CRYO says so rather than force an
          answer.
        </p>
        <a href="#/docs">Read the answer contract <span aria-hidden="true">→</span></a>
      </section>
    </>
  )
}
