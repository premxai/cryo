import { useCallback, useEffect, useRef, useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL || ''
const DEFAULTS = { yearMin: 2000, yearMax: 2021, domain: '', contentType: '' }

function readUrlState() {
  const p = new URLSearchParams(window.location.search)
  return {
    q: p.get('q') || '',
    yearMin: parseInt(p.get('year_min') || '2000'),
    yearMax: parseInt(p.get('year_max') || '2021'),
    sort: p.get('sort') || 'relevance',
    domain: p.get('domain') || '',
    contentType: p.get('content_type') || '',
  }
}

function writeUrlState(state) {
  const p = new URLSearchParams()
  if (state.q) p.set('q', state.q)
  if (state.yearMin !== 2000) p.set('year_min', state.yearMin)
  if (state.yearMax !== 2021) p.set('year_max', state.yearMax)
  if (state.sort !== 'relevance') p.set('sort', state.sort)
  if (state.domain) p.set('domain', state.domain)
  if (state.contentType) p.set('content_type', state.contentType)
  const qs = p.toString()
  const path = window.location.pathname
  const hash = window.location.hash || '#/'
  window.history.replaceState({}, '', qs ? `${path}?${qs}${hash}` : path + hash)
}

/**
 * useCorpusSearch — all search state + fetching against the legacy /search,
 * /facets endpoints. Shared by the landing teaser (auto=false, capped) and the
 * authenticated console (auto=true, unlimited).
 *
 * @param {object}  opts
 * @param {number}  opts.pageSize  results per request
 * @param {boolean} opts.auto      debounce-search as query/filters change
 * @param {boolean} opts.syncUrl   mirror query/filters into the URL
 */
export function useCorpusSearch({ pageSize = 20, auto = true, syncUrl = true } = {}) {
  const initial = syncUrl ? readUrlState() : { q: '', ...DEFAULTS, sort: 'relevance' }

  const [query, setQuery] = useState(initial.q)
  const [filters, setFilters] = useState({
    yearMin: initial.yearMin, yearMax: initial.yearMax,
    domain: initial.domain, contentType: initial.contentType,
  })
  const [sort, setSort] = useState(initial.sort)

  const [results, setResults] = useState([])
  const [total, setTotal] = useState(0)
  const [facets, setFacets] = useState({})
  const [searchTimeMs, setSearchTimeMs] = useState(null)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState(null)
  const [offset, setOffset] = useState(0)

  const timer = useRef(null)

  const runSearch = useCallback(async (q, f, s, off, append) => {
    if (!q.trim()) { setResults([]); setTotal(0); setSearchTimeMs(null); return }
    append ? setLoadingMore(true) : setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({
        q, year_min: f.yearMin, year_max: f.yearMax, sort: s, limit: pageSize, offset: off,
      })
      if (f.domain) params.set('domain', f.domain)
      if (f.contentType) params.set('content_type', f.contentType)
      const res = await fetch(`${API_URL}/search?${params}`)
      if (!res.ok) throw new Error(`Search failed (${res.status})`)
      const data = await res.json()
      setResults((prev) => (append ? [...prev, ...data.results] : data.results))
      setTotal(data.total)
      setSearchTimeMs(data.search_time_ms)
      if (data.facets && Object.keys(data.facets).length) setFacets(data.facets)
      document.title = 'Cryo'
    } catch (err) {
      setError(err.message || 'Search failed. Is the backend running?')
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [pageSize])

  // Facets on mount + run any initial URL query.
  useEffect(() => {
    fetch(`${API_URL}/facets`).then((r) => r.json()).then(setFacets).catch(() => {})
    if (initial.q) runSearch(initial.q, filters, sort, 0, false)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Optional debounced auto-search.
  useEffect(() => {
    if (!auto) return
    clearTimeout(timer.current)
    if (syncUrl) writeUrlState({ q: query, ...filters, sort })
    if (!query.trim()) { setResults([]); setTotal(0); setSearchTimeMs(null); return }
    timer.current = setTimeout(() => { setOffset(0); runSearch(query, filters, sort, 0, false) }, 300)
    return () => clearTimeout(timer.current)
  }, [query, filters, sort, auto, syncUrl, runSearch])

  const loadMore = useCallback(() => {
    const next = offset + pageSize
    setOffset(next)
    runSearch(query, filters, sort, next, true)
  }, [offset, pageSize, query, filters, sort, runSearch])

  const reset = useCallback(() => {
    setResults([]); setTotal(0); setSearchTimeMs(null); setError(null); setOffset(0)
  }, [])

  const hasMore = results.length < total && results.length > 0

  return {
    query, setQuery, filters, setFilters, sort, setSort,
    results, total, facets, searchTimeMs, loading, loadingMore, error,
    offset, setOffset, runSearch, loadMore, hasMore, reset,
  }
}
