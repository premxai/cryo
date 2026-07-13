import { useEffect, useRef, useState } from 'react'
import ErrorBoundary from './ErrorBoundary'
import ResultCard from './ResultCard'

function ResultSkeleton() {
  return (
    <div className="result-skeleton">
      <div className="bar short" />
      <div className="bar long" />
      <div className="bar long" style={{ width: '60%' }} />
    </div>
  )
}

/**
 * ResultLedger — the archive result ledger shared by the landing teaser and the
 * authenticated console. Handles head, skeletons, rows, states, load-more,
 * keyboard nav (↑↓ + Enter to open), and an optional footer/overlay slot.
 */
export default function ResultLedger({
  results, total, searchTimeMs, loading, loadingMore, error, hasMore,
  onLoadMore, onRetry, query, headLabel, showLoadMore = true, footer, overlay,
}) {
  const [focusedIndex, setFocusedIndex] = useState(-1)
  const resultRefs = useRef([])

  useEffect(() => {
    const handler = (e) => {
      if (document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA') return
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setFocusedIndex((i) => {
          const next = Math.min(i + 1, results.length - 1)
          resultRefs.current[next]?.scrollIntoView({ block: 'nearest' })
          return next
        })
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setFocusedIndex((i) => {
          const prev = Math.max(i - 1, 0)
          resultRefs.current[prev]?.scrollIntoView({ block: 'nearest' })
          return prev
        })
      } else if (e.key === 'Enter' && focusedIndex >= 0) {
        const url = results[focusedIndex]?.url
        if (url) window.open(url, '_blank', 'noopener,noreferrer')
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [results, focusedIndex])

  const hasQuery = Boolean(query?.trim())

  return (
    <div className="result-ledger">
      <div className="ledger-head">
        <span>
          {headLabel !== undefined
            ? headLabel
            : hasQuery && searchTimeMs !== null
              ? `${total.toLocaleString()} records / ${searchTimeMs}ms`
              : 'Live corpus index'}
        </span>
        <span>CAPTURED BEFORE 2022</span>
        <span>AUTHENTICITY</span>
      </div>

      {error && (
        <div className="ledger-error">
          {error}
          {onRetry && <button onClick={onRetry}>Retry</button>}
        </div>
      )}

      {loading && (
        <div>{Array.from({ length: 5 }).map((_, i) => <ResultSkeleton key={i} />)}</div>
      )}

      {!loading && (
        <ErrorBoundary>
          <div>
            {results.map((result, i) => (
              <div
                key={result.id}
                ref={(el) => (resultRefs.current[i] = el)}
                style={focusedIndex === i ? { background: 'var(--paper-deep)' } : undefined}
                onMouseEnter={() => setFocusedIndex(i)}
              >
                <ResultCard result={result} index={i} />
              </div>
            ))}
          </div>
        </ErrorBoundary>
      )}

      {overlay}

      {!loading && !error && hasQuery && results.length === 0 && searchTimeMs !== null && !overlay && (
        <div className="ledger-note">
          No record matched “{query}”. Try broader terms or clear a filter. A production
          search explains zero results without inventing them.
        </div>
      )}

      {!loading && showLoadMore && hasMore && (
        <button className="load-more" onClick={onLoadMore} disabled={loadingMore}>
          {loadingMore ? 'Loading…' : `Load more · ${(total - results.length).toLocaleString()} remaining`}
        </button>
      )}

      {footer}
    </div>
  )
}
