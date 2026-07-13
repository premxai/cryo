/**
 * AppSearch — the authenticated search console. Full filter sidebar, unlimited
 * results with pagination, live debounced search. Redirects to sign-in when no
 * session is present.
 */

import { useEffect, useRef } from "react";
import AutocompleteInput from "./AutocompleteInput";
import FilterSidebar from "./FilterSidebar";
import ResultLedger from "./ResultLedger";
import { useCorpusSearch } from "./useCorpusSearch";
import { useSession } from "./useSession";

export default function AppSearch() {
  const session = useSession();
  const inputRef = useRef(null);

  const {
    query, setQuery, filters, setFilters, sort, setSort,
    results, total, facets, searchTimeMs, loading, loadingMore, error,
    runSearch, loadMore, hasMore, setOffset,
  } = useCorpusSearch({ pageSize: 20, auto: true, syncUrl: true });

  // Auth gate — bounce to the magic-link sign-in.
  useEffect(() => {
    if (!session) window.location.hash = "#/dashboard";
  }, [session]);

  if (!session) return null;

  return (
    <>
      <section className="dashboard-top">
        <p className="eyebrow"><span></span> SEARCH CONSOLE / {session.email}</p>
        <h1>Search the<br /><em>frozen web.</em></h1>
        <p>Unlimited searches over the full pre-2022 corpus, with filters and pagination.</p>
      </section>

      <section className="search-shell" aria-label="Search console">
        <div className="search-intro">
          <div style={{ marginBottom: "2rem" }}>
            <AutocompleteInput
              value={query}
              onChange={setQuery}
              onSearch={(q) => { setOffset(0); runSearch(q, filters, sort, 0, false); }}
              inputRef={inputRef}
            />
          </div>
          <FilterSidebar
            filters={filters}
            facets={facets}
            sort={sort}
            onFilterChange={(f) => { setFilters(f); setOffset(0); }}
            onSortChange={(s) => { setSort(s); setOffset(0); }}
          />
          <p className="side-note" style={{ marginTop: "2rem" }}>
            <a href="#/dashboard" style={{ color: "var(--blue)" }}>Manage keys &amp; usage →</a>
          </p>
        </div>

        <ResultLedger
          results={results}
          total={total}
          searchTimeMs={searchTimeMs}
          loading={loading}
          loadingMore={loadingMore}
          error={error}
          hasMore={hasMore}
          onLoadMore={loadMore}
          onRetry={() => runSearch(query, filters, sort, 0, false)}
          query={query}
          footer={
            <div className="ledger-foot">
              <p><i className="signal scored"></i><b>Scored</b> means a judge result exists.</p>
              <p><i className="signal unscored"></i><b>Unscored</b> is a distinct state, not a certification claim.</p>
              <a href={`#/ask?q=${encodeURIComponent(query.trim())}`}>Ask from these sources <span aria-hidden="true">→</span></a>
            </div>
          }
        />
      </section>
    </>
  );
}
