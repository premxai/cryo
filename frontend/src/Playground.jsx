import { useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL || ''

const EXAMPLES = [
  'What did people think about remote work before 2022?',
  'How did early startups approach fundraising?',
  'What was the culture of the early web like?',
]

/**
 * Render answer text with [n] citation markers as superscript anchors.
 */
function AnswerText({ text }) {
  const parts = text.split(/(\[\d+\])/g)
  return (
    <p className="text-sm text-white/75 leading-relaxed whitespace-pre-wrap">
      {parts.map((part, i) => {
        const m = part.match(/^\[(\d+)\]$/)
        if (!m) return <span key={i}>{part}</span>
        return (
          <a key={i} href={`#cite-${m[1]}`} className="text-[#4a9eff] text-xs align-super mx-0.5">
            [{m[1]}]
          </a>
        )
      })}
    </p>
  )
}

function Citation({ c }) {
  const date = c.timestamp
    ? `${c.timestamp.slice(0, 4)}-${c.timestamp.slice(4, 6)}-${c.timestamp.slice(6, 8)}`
    : ''
  return (
    <div id={`cite-${c.index}`} className="liquid-glass rounded-xl px-4 py-3 flex items-start gap-3">
      <span className="text-xs text-[#4a9eff] shrink-0 mt-0.5" style={{ fontFamily: 'var(--font-mono)' }}>
        [{c.index}]
      </span>
      <div className="min-w-0 flex-1">
        <a
          href={c.archive_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-white/60 hover:text-white/90 transition-colors truncate block"
          style={{ fontFamily: 'var(--font-mono)' }}
          title={c.url}
        >
          {c.url}
        </a>
        <div className="flex items-center gap-3 mt-1.5 text-[10px] text-white/30 font-light">
          <span style={{ fontFamily: 'var(--font-mono)' }}>❄ frozen {date}</span>
          {c.human_score != null && (
            <span>human score {(c.human_score * 100).toFixed(0)}%</span>
          )}
          {c.cryo_certified && <span className="text-emerald-400/60">✓ certified</span>}
          <a
            href={c.archive_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-white/20 hover:text-[#4a9eff]/60 transition-colors"
          >
            view snapshot ↗
          </a>
        </div>
      </div>
    </div>
  )
}

/**
 * Playground — "ask the pre-AI web": live /v1/answer demo via the rate-limited
 * server-side proxy (no API key in the browser).
 */
export default function Playground() {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function ask(q) {
    const question = (q ?? query).trim()
    if (question.length < 3 || loading) return
    setQuery(question)
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const r = await fetch(`${API_URL}/demo/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: question }),
      })
      const data = await r.json()
      if (!r.ok) throw new Error(data?.error?.message || `Request failed (${r.status})`)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full max-w-2xl pb-16">
      <h1 className="gradient-heading text-3xl mb-2">Ask the pre-AI web</h1>
      <p className="text-sm text-white/50 mb-8 font-light">
        Answers grounded only in archived pre-2022 pages — every citation is a frozen
        snapshot with an authenticity score. Nothing here can be AI-contaminated, by construction.
      </p>

      <form
        onSubmit={(e) => { e.preventDefault(); ask() }}
        className="flex gap-2 mb-4"
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask a question…"
          maxLength={500}
          className="flex-1 liquid-glass rounded-full px-5 py-3 text-sm bg-transparent text-white placeholder-white/30 focus:outline-none"
        />
        <button
          type="submit"
          disabled={loading}
          className="liquid-glass rounded-full px-6 py-3 text-sm text-white/80 hover:text-white transition-colors disabled:opacity-40"
        >
          {loading ? 'Thinking…' : 'Ask'}
        </button>
      </form>

      {!result && !loading && (
        <div className="flex flex-wrap gap-2 mb-8">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              onClick={() => ask(ex)}
              className="text-xs text-white/30 hover:text-white/60 liquid-glass rounded-full px-3 py-1.5 transition-colors font-light"
            >
              {ex}
            </button>
          ))}
        </div>
      )}

      {loading && (
        <div className="liquid-glass rounded-xl p-5 animate-pulse">
          <div className="h-3 w-3/4 bg-white/5 rounded mb-2" />
          <div className="h-3 w-full bg-white/[0.03] rounded mb-2" />
          <div className="h-3 w-5/6 bg-white/[0.03] rounded" />
          <div className="text-[10px] text-white/20 mt-4 font-light">
            reading the frozen archive…
          </div>
        </div>
      )}

      {error && (
        <div className="liquid-glass rounded-xl p-4 text-sm text-red-400/80 font-light">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-6">
          <div className="liquid-glass-strong rounded-xl p-5">
            <AnswerText text={result.answer} />
            <div className="text-[10px] text-white/20 mt-4 font-light">
              {result.cached ? 'cached · ' : ''}model: {result.model}
            </div>
          </div>
          <div>
            <div className="text-xs text-white/40 mb-3 tracking-wide">
              FROZEN SOURCES · all captured before 2022
            </div>
            <div className="space-y-2">
              {result.citations.map((c) => <Citation key={c.index} c={c} />)}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
