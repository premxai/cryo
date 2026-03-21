/**
 * Search — main search interface with:
 * - Debounced autocomplete (150ms suggest, 300ms search)
 * - Keyboard shortcuts: '/' to focus, Esc to clear, ↑↓ to navigate results, Enter to open
 * - URL-synced state (back button works, searches are shareable)
 * - Filter sidebar (year range, domain, content type, sort)
 * - Pagination via "Load more" button
 * - Highlighted matched terms in results
 */

import { useCallback, useEffect, useRef, useState } from "react";
import AutocompleteInput from "./AutocompleteInput";
import ErrorBoundary from "./ErrorBoundary";
import FilterSidebar from "./FilterSidebar";
import ResultCard from "./ResultCard";

const API_URL = import.meta.env.VITE_API_URL || "";
const PAGE_SIZE = 20;

function readUrlState() {
  const p = new URLSearchParams(window.location.search);
  return {
    q: p.get("q") || "",
    yearMin: parseInt(p.get("year_min") || "2000"),
    yearMax: parseInt(p.get("year_max") || "2021"),
    sort: p.get("sort") || "relevance",
    domain: p.get("domain") || "",
    contentType: p.get("content_type") || "",
  };
}

function writeUrlState(state) {
  const p = new URLSearchParams();
  if (state.q) p.set("q", state.q);
  if (state.yearMin !== 2000) p.set("year_min", state.yearMin);
  if (state.yearMax !== 2021) p.set("year_max", state.yearMax);
  if (state.sort !== "relevance") p.set("sort", state.sort);
  if (state.domain) p.set("domain", state.domain);
  if (state.contentType) p.set("content_type", state.contentType);
  const qs = p.toString();
  window.history.pushState({}, "", qs ? `?${qs}` : window.location.pathname);
}

function ResultSkeleton() {
  return (
    <div className="border-b border-[#1e2d45] pb-6 pt-4 animate-pulse">
      <div className="h-3 w-48 bg-[#1e2d45] mb-3" />
      <div className="h-4 w-3/4 bg-[#1e2d45] mb-2" />
      <div className="h-3 w-full bg-[#1a2535] mb-1" />
      <div className="h-3 w-5/6 bg-[#1a2535]" />
    </div>
  );
}

export default function Search() {
  const initial = readUrlState();

  const [query, setQuery] = useState(initial.q);
  const [filters, setFilters] = useState({
    yearMin: initial.yearMin,
    yearMax: initial.yearMax,
    domain: initial.domain,
    contentType: initial.contentType,
  });
  const [sort, setSort] = useState(initial.sort);

  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [facets, setFacets] = useState({});
  const [searchTimeMs, setSearchTimeMs] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);
  const [offset, setOffset] = useState(0);
  const [focusedIndex, setFocusedIndex] = useState(-1);

  const inputRef = useRef(null);
  const searchTimerRef = useRef(null);
  const resultRefs = useRef([]);

  // ── Fetch global facets on mount ───────────────────────────────────────────
  useEffect(() => {
    fetch(`${API_URL}/facets`)
      .then((r) => r.json())
      .then(setFacets)
      .catch(() => {});

    // Run search if URL has a query on load
    if (initial.q) {
      runSearch(initial.q, { yearMin: initial.yearMin, yearMax: initial.yearMax, domain: initial.domain, contentType: initial.contentType }, initial.sort, 0, false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Run search ─────────────────────────────────────────────────────────────
  const runSearch = useCallback(async (q, currentFilters, currentSort, currentOffset, append) => {
    if (!q.trim()) {
      setResults([]);
      setTotal(0);
      setSearchTimeMs(null);
      return;
    }

    append ? setLoadingMore(true) : setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        q,
        year_min: currentFilters.yearMin,
        year_max: currentFilters.yearMax,
        sort: currentSort,
        limit: PAGE_SIZE,
        offset: currentOffset,
      });
      if (currentFilters.domain) params.set("domain", currentFilters.domain);
      if (currentFilters.contentType) params.set("content_type", currentFilters.contentType);

      const res = await fetch(`${API_URL}/search?${params}`);
      if (!res.ok) throw new Error(`Search failed (${res.status})`);
      const data = await res.json();

      setResults((prev) => (append ? [...prev, ...data.results] : data.results));
      setTotal(data.total);
      setSearchTimeMs(data.search_time_ms);
      if (data.facets && Object.keys(data.facets).length) setFacets(data.facets);
      setFocusedIndex(-1);
      document.title = q ? `${q} – Cryo` : "Cryo";
    } catch (err) {
      setError(err.message || "Search failed. Is the backend running?");
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  // ── Debounce search on state changes ──────────────────────────────────────
  useEffect(() => {
    clearTimeout(searchTimerRef.current);
    writeUrlState({ q: query, ...filters, sort });
    if (!query.trim()) { setResults([]); setTotal(0); setSearchTimeMs(null); return; }
    searchTimerRef.current = setTimeout(() => {
      setOffset(0);
      runSearch(query, filters, sort, 0, false);
    }, 300);
    return () => clearTimeout(searchTimerRef.current);
  }, [query, filters, sort]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Browser back/forward ───────────────────────────────────────────────────
  useEffect(() => {
    const handler = () => {
      const s = readUrlState();
      setQuery(s.q);
      setFilters({ yearMin: s.yearMin, yearMax: s.yearMax, domain: s.domain, contentType: s.contentType });
      setSort(s.sort);
    };
    window.addEventListener("popstate", handler);
    return () => window.removeEventListener("popstate", handler);
  }, []);

  // ── Global keyboard shortcuts ──────────────────────────────────────────────
  useEffect(() => {
    const handler = (e) => {
      if (e.key === "/" && document.activeElement !== inputRef.current && e.target.tagName !== "INPUT") {
        e.preventDefault();
        inputRef.current?.focus();
        return;
      }
      if (document.activeElement === inputRef.current) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setFocusedIndex((i) => {
          const next = Math.min(i + 1, results.length - 1);
          resultRefs.current[next]?.scrollIntoView({ block: "nearest" });
          return next;
        });
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setFocusedIndex((i) => {
          const prev = Math.max(i - 1, 0);
          resultRefs.current[prev]?.scrollIntoView({ block: "nearest" });
          return prev;
        });
      } else if (e.key === "Enter" && focusedIndex >= 0) {
        const url = results[focusedIndex]?.url;
        if (url) window.open(url, "_blank", "noopener,noreferrer");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [results, focusedIndex]);

  function loadMore() {
    const newOffset = offset + PAGE_SIZE;
    setOffset(newOffset);
    runSearch(query, filters, sort, newOffset, true);
  }

  const hasMore = results.length < total && results.length > 0;

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Search input */}
      <div className="mb-6">
        <AutocompleteInput
          value={query}
          onChange={setQuery}
          onSearch={(q) => { setOffset(0); runSearch(q, filters, sort, 0, false); }}
          inputRef={inputRef}
        />
        <div className="mt-1 text-[10px] text-[#2d3a4a] text-right select-none">
          <kbd className="bg-[#1a2535] border border-[#1e2d45] px-1">/</kbd> focus ·{" "}
          <kbd className="bg-[#1a2535] border border-[#1e2d45] px-1">↑↓</kbd> navigate ·{" "}
          <kbd className="bg-[#1a2535] border border-[#1e2d45] px-1">↵</kbd> open
        </div>
      </div>

      <div className="flex gap-8">
        {/* Filter sidebar */}
        <FilterSidebar
          filters={filters}
          facets={facets}
          sort={sort}
          onFilterChange={(f) => { setFilters(f); setOffset(0); }}
          onSortChange={(s) => { setSort(s); setOffset(0); }}
        />

        {/* Results */}
        <div className="flex-1 min-w-0">
          {/* Stats */}
          {!loading && query && searchTimeMs !== null && (
            <div className="text-xs text-[#4a5568] mb-5">
              <span className="text-[#a0aec0] font-mono">{total.toLocaleString()}</span> results in{" "}
              <span className="text-[#a0aec0] font-mono">{searchTimeMs}ms</span>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="border border-red-900/50 bg-red-950/10 p-4 text-sm text-red-400 mb-6">
              {error}
              <button onClick={() => runSearch(query, filters, sort, 0, false)} className="ml-3 underline">
                Retry
              </button>
            </div>
          )}

          {/* Skeletons */}
          {loading && (
            <div className="space-y-0 divide-y divide-[#1e2d45]">
              {Array.from({ length: 5 }).map((_, i) => <ResultSkeleton key={i} />)}
            </div>
          )}

          {/* Result list */}
          {!loading && (
            <ErrorBoundary>
              <div>
                {results.map((result, i) => (
                  <div
                    key={result.id}
                    ref={(el) => (resultRefs.current[i] = el)}
                    className={`transition-colors duration-100 ${
                      focusedIndex === i ? "bg-[#0c1420]" : ""
                    }`}
                    onMouseEnter={() => setFocusedIndex(i)}
                  >
                    <ResultCard result={result} query={query} />
                  </div>
                ))}
              </div>
            </ErrorBoundary>
          )}

          {/* Zero results */}
          {!loading && !error && query && results.length === 0 && searchTimeMs !== null && (
            <div className="text-center py-16 text-[#4a5568]">
              <div className="text-3xl mb-3 opacity-40">∅</div>
              <div className="text-sm mb-1">
                No results for <span className="text-[#a0aec0]">"{query}"</span>
              </div>
              <div className="text-xs mt-1">Try broader terms or adjust filters.</div>
            </div>
          )}

          {/* Load more */}
          {!loading && hasMore && (
            <div className="mt-10 text-center">
              <button
                onClick={loadMore}
                disabled={loadingMore}
                className="border border-[#1e2d45] text-[#a0aec0] hover:border-[#4a9eff] hover:text-[#4a9eff]
                           px-8 py-2 text-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {loadingMore ? "Loading…" : `Load more · ${total - results.length} remaining`}
              </button>
            </div>
          )}

          {/* Empty state */}
          {!query && !loading && (
            <div className="text-center py-24 select-none">
              <div className="text-5xl mb-5 opacity-10">❄</div>
              <div className="text-sm text-[#2d3a4a]">The human web. Preserved.</div>
              <div className="text-xs text-[#1e2d45] mt-2">Pre-2022 · BM25 search · No AI content</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
