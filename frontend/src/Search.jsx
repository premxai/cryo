/**
 * Search — archive-editorial home: frozen-cube hero + live result ledger.
 * - Debounced autocomplete (150ms suggest, 300ms search)
 * - Keyboard shortcuts: '/' to focus, ↑↓ to navigate results, Enter to open
 * - URL-synced state (back button works, searches are shareable)
 * - Filters (year range, domain, content type, sort) + "Load more" pagination
 */

import { useCallback, useEffect, useRef, useState } from "react";
import AutocompleteInput from "./AutocompleteInput";
import ErrorBoundary from "./ErrorBoundary";
import FilterSidebar from "./FilterSidebar";
import ResultCard from "./ResultCard";
import cubeImg from "./assets/frozen-corpus-cube.jpg";

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
  const base = window.location.pathname + (window.location.hash || "#/");
  window.history.replaceState({}, "", qs ? `${window.location.pathname}?${qs}${window.location.hash}` : base);
}

function ResultSkeleton() {
  return (
    <div className="result-skeleton">
      <div className="bar short" />
      <div className="bar long" />
      <div className="bar long" style={{ width: "60%" }} />
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
  const ledgerRef = useRef(null);

  // ── Fetch global facets on mount + run search if URL has a query ──────────
  useEffect(() => {
    fetch(`${API_URL}/facets`)
      .then((r) => r.json())
      .then(setFacets)
      .catch(() => {});

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
      document.title = q ? `${q} — CRYO` : "CRYO — The web before the AI web.";
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

  // ── Global keyboard shortcuts ──────────────────────────────────────────────
  useEffect(() => {
    const handler = (e) => {
      if (e.key === "/" && document.activeElement !== inputRef.current && e.target.tagName !== "INPUT" && e.target.tagName !== "TEXTAREA") {
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

  function onSubmitSearch(q) {
    setOffset(0);
    runSearch(q, filters, sort, 0, false);
    ledgerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const hasMore = results.length < total && results.length > 0;
  const hasQuery = Boolean(query.trim());
  const askHref = `#/ask?q=${encodeURIComponent(query.trim())}`;

  return (
    <>
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow"><span></span> ARCHIVE INDEX / CUT OFF 2022-01-01</p>
          <h1>The web<br />before the<br /><em>AI web.</em></h1>
          <p className="lede">
            Search infrastructure for a frozen pre-2022 corpus. Every result carries its
            capture record and an honest human-authenticity state.
          </p>
          <AutocompleteInput
            value={query}
            onChange={setQuery}
            onSearch={onSubmitSearch}
            inputRef={inputRef}
          />
          <div className="hero-footnotes">
            <p><b>FROZEN CUTOFF</b><strong>2022–01–01</strong><small>00:00:00 UTC</small></p>
            <p>Not a feed. Not a rewrite.<br />An inspectable corpus for people and agents.</p>
          </div>
        </div>
        <figure className="archive-figure" aria-labelledby="artifact-caption">
          <img
            src={cubeImg}
            alt="A monumental cube of clear ice preserving dense stacks of pre-2022 paper documents."
          />
          <figcaption id="artifact-caption">
            <span>FROZEN CORPUS</span>
            <b>Source, archive, timestamp.</b>
            <small>Every result keeps its trail.</small>
          </figcaption>
        </figure>
      </section>

      {/* ── Search shell ─────────────────────────────────────────────────── */}
      <section className="search-shell" aria-labelledby="results-heading" ref={ledgerRef}>
        <div className="search-intro">
          <p className="eyebrow"><span></span> PROOF SURFACE / LIVE CORPUS</p>
          <h2 id="results-heading">Inspect the<br /><em>record.</em></h2>
          <p>
            Results come straight from <code>/v1/search</code> — BM25 keyword retrieval with a
            semantic re-rank. Each row keeps its source ledger.
          </p>
          <FilterSidebar
            filters={filters}
            facets={facets}
            sort={sort}
            onFilterChange={(f) => { setFilters(f); setOffset(0); }}
            onSortChange={(s) => { setSort(s); setOffset(0); }}
          />
        </div>

        <div className="result-ledger">
          <div className="ledger-head">
            <span>
              {hasQuery && searchTimeMs !== null
                ? `${total.toLocaleString()} records / ${searchTimeMs}ms`
                : "Live corpus index"}
            </span>
            <span>CAPTURED BEFORE 2022</span>
            <span>AUTHENTICITY</span>
          </div>

          {error && (
            <div className="ledger-error">
              {error}
              <button onClick={() => runSearch(query, filters, sort, 0, false)}>Retry</button>
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
                    style={focusedIndex === i ? { background: "var(--paper-deep)" } : undefined}
                    onMouseEnter={() => setFocusedIndex(i)}
                  >
                    <ResultCard result={result} index={i} />
                  </div>
                ))}
              </div>
            </ErrorBoundary>
          )}

          {!loading && !error && hasQuery && results.length === 0 && searchTimeMs !== null && (
            <div className="ledger-note">
              No record matched “{query}”. Try broader terms or clear a filter. A production
              search explains zero results without inventing them.
            </div>
          )}

          {!loading && !hasQuery && (
            <div className="ledger-note">
              Enter a query above to search the frozen corpus. Filters compose with the query;
              scored and unscored are distinct, honestly-labeled states.
            </div>
          )}

          {!loading && hasMore && (
            <button className="load-more" onClick={loadMore} disabled={loadingMore}>
              {loadingMore ? "Loading…" : `Load more · ${(total - results.length).toLocaleString()} remaining`}
            </button>
          )}

          <div className="ledger-foot">
            <p><i className="signal scored"></i><b>Scored</b> means a judge result exists.</p>
            <p><i className="signal unscored"></i><b>Unscored</b> is a distinct state, not a certification claim.</p>
            <a href={askHref}>Ask from these sources <span aria-hidden="true">→</span></a>
          </div>
        </div>
      </section>

      {/* ── Promise band ─────────────────────────────────────────────────── */}
      <section className="promise-band">
        <p className="eyebrow"><span></span> A SEARCH API WITH RECEIPTS</p>
        <div>
          <h2>The result is more<br />than a <em>snippet.</em></h2>
          <p>
            URL, archive URL, captured timestamp, domain, and human score travel together. The
            same source ledger powers Search, Ask, and every agent call.
          </p>
        </div>
        <div className="promise-index">
          <span>01 / SEARCH</span>
          <span>02 / ASK</span>
          <span>03 / BUILD</span>
        </div>
      </section>

      {/* ── The loop: how an agent uses it ───────────────────────────────── */}
      <section className="endpoint-section">
        <p className="eyebrow"><span></span> THE LOOP / SEARCH → READ → BROWSE → ASK</p>
        <h2>Built for agents that<br /><em>show their work.</em></h2>
        <div className="endpoint-list cols-4">
          <article>
            <code>01 / SEARCH</code>
            <p>Query the frozen corpus. Every hit returns its URL, capture date, domain, and authenticity state.</p>
            <span>cryo_search</span>
          </article>
          <article>
            <code>02 / READ</code>
            <p>Pull full page text by id or URL. Missing pages are fetched live from pre-2022 Wayback snapshots and frozen in.</p>
            <span>cryo_get_page</span>
          </article>
          <article>
            <code>03 / BROWSE</code>
            <p>Enumerate a domain's captured archive to walk an era of a site, not just one page.</p>
            <span>cryo_list_domain</span>
          </article>
          <article>
            <code>04 / ASK</code>
            <p>Grounded synthesis citing only frozen snapshots — every claim traces back to a ledger entry.</p>
            <span>cryo_answer</span>
          </article>
        </div>
      </section>

      {/* ── Four ways in ─────────────────────────────────────────────────── */}
      <section className="docs-two-up">
        <article>
          <p className="eyebrow"><span></span> WHY A FROZEN CORPUS</p>
          <h2>The web is filling<br />with <em>machine text.</em></h2>
          <p>
            Cryo indexes only content captured before 2022 — before generative models began
            flooding the open web. Its answers cannot be contaminated by AI-written pages, by
            construction, and it proves it per document: capture timestamp, source, archive link,
            and an authenticity score.
          </p>
          <a href="#/docs">Read the methodology <span aria-hidden="true">→</span></a>
        </article>
        <article>
          <p className="eyebrow"><span></span> FOUR WAYS IN</p>
          <h2>However your<br />stack works.</h2>
          <dl>
            <div><dt>REST</dt><dd>POST /v1/search · /contents · /answer · /find-similar · /list-domain</dd></div>
            <div><dt>SDK</dt><dd>pip install cryo-search — typed client with retries and the full ledger</dd></div>
            <div><dt>Agents</dt><dd>CryoSearchTool + CryoAnswerTool for LangChain / LlamaIndex</dd></div>
            <div><dt>MCP</dt><dd>Five native tools for Claude Code &amp; Desktop at /mcp</dd></div>
          </dl>
          <a href="#/docs">Open the docs <span aria-hidden="true">→</span></a>
        </article>
      </section>
    </>
  );
}
