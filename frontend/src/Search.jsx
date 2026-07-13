/**
 * Search — archive-editorial landing: frozen-cube hero + a gated teaser search.
 * Anonymous visitors get 15 results per search and 5 free searches, then a
 * login wall. Signed-in visitors are pointed to the full search console (#/app).
 */

import { useRef, useState } from "react";
import AutocompleteInput from "./AutocompleteInput";
import ResultLedger from "./ResultLedger";
import { useCorpusSearch } from "./useCorpusSearch";
import { useSession } from "./useSession";
import cubeImg from "./assets/frozen-corpus-cube.jpg";

const TEASER_RESULTS = 15;
const FREE_LIMIT = 5;
const FREE_KEY = "cryo_free_searches";

export default function Search() {
  const session = useSession();
  const inputRef = useRef(null);
  const ledgerRef = useRef(null);

  const {
    query, setQuery, filters, sort,
    results, total, searchTimeMs, loading, error, runSearch,
  } = useCorpusSearch({ pageSize: TEASER_RESULTS, auto: false, syncUrl: false });

  const [freeUsed, setFreeUsed] = useState(() => parseInt(localStorage.getItem(FREE_KEY) || "0"));
  const [walled, setWalled] = useState(false);

  const remaining = Math.max(0, FREE_LIMIT - freeUsed);

  function onSubmit(q) {
    const term = (q ?? query).trim();
    if (!term) return;
    // Signed-in visitors have no teaser cap.
    if (session) { runSearch(term, filters, sort, 0, false); scrollToLedger(); return; }
    if (freeUsed >= FREE_LIMIT) { setWalled(true); scrollToLedger(); return; }
    const n = freeUsed + 1;
    localStorage.setItem(FREE_KEY, String(n));
    setFreeUsed(n);
    runSearch(term, filters, sort, 0, false);
    scrollToLedger();
  }

  function scrollToLedger() {
    ledgerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const loginWall = (walled || (!session && freeUsed >= FREE_LIMIT && !results.length)) ? (
    <div className="ledger-note" style={{ borderBottom: "1px solid var(--ink)" }}>
      <p style={{ font: "500 1.15rem var(--body)", margin: "0 0 .6rem", color: "var(--ink)" }}>
        You’ve used all {FREE_LIMIT} free searches.
      </p>
      <p style={{ margin: "0 0 1rem" }}>
        Sign in for unlimited searches, full filters, and the search console. No password —
        we send a magic link.
      </p>
      <a className="ink-button" href="#/dashboard" style={{ display: "inline-block" }}>
        Sign in for unlimited <span aria-hidden="true">→</span>
      </a>
    </div>
  ) : null;

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
          <AutocompleteInput value={query} onChange={setQuery} onSearch={onSubmit} inputRef={inputRef} />
          <div className="hero-footnotes">
            <p><b>FROZEN CUTOFF</b><strong>2022–01–01</strong><small>00:00:00 UTC</small></p>
            <p>Not a feed. Not a rewrite.<br />An inspectable corpus for people and agents.</p>
          </div>
        </div>
        <figure className="archive-figure" aria-labelledby="artifact-caption">
          <img src={cubeImg} alt="A monumental cube of clear ice preserving dense stacks of pre-2022 paper documents." />
          <figcaption id="artifact-caption">
            <span>FROZEN CORPUS</span>
            <b>Source, archive, timestamp.</b>
            <small>Every result keeps its trail.</small>
          </figcaption>
        </figure>
      </section>

      {/* ── Teaser search ledger ─────────────────────────────────────────── */}
      <section className="search-shell" aria-labelledby="results-heading" ref={ledgerRef}>
        <div className="search-intro">
          <p className="eyebrow"><span></span> PROOF SURFACE / LIVE CORPUS</p>
          <h2 id="results-heading">Inspect the<br /><em>record.</em></h2>
          <p>
            Results come straight from <code>/v1/search</code> — BM25 keyword retrieval with a
            semantic re-rank. Each row keeps its source ledger.
          </p>
          {session ? (
            <div className="filter-block">
              <div className="filter-label">Signed in</div>
              <a className="ink-button" href="#/app" style={{ display: "inline-block" }}>
                Open search console <span aria-hidden="true">→</span>
              </a>
              <p className="side-note">Unlimited searches, full filters, and pagination.</p>
            </div>
          ) : (
            <div className="filter-block">
              <div className="filter-label">Free preview</div>
              <p className="side-note" style={{ marginTop: ".4rem" }}>
                {remaining} of {FREE_LIMIT} free searches left · {TEASER_RESULTS} results each.
                <br />
                <a href="#/dashboard" style={{ color: "var(--blue)", textDecoration: "underline", textUnderlineOffset: "3px" }}>
                  Sign in
                </a>{" "}
                for unlimited searches and full filters.
              </p>
            </div>
          )}
        </div>

        <ResultLedger
          results={results}
          total={total}
          searchTimeMs={searchTimeMs}
          loading={loading}
          loadingMore={false}
          error={error}
          hasMore={false}
          onRetry={() => onSubmit(query)}
          query={query}
          headLabel={
            !query.trim()
              ? "Live corpus index"
              : searchTimeMs !== null
                ? `Showing top ${Math.min(results.length, TEASER_RESULTS)} of ${total.toLocaleString()}`
                : undefined
          }
          showLoadMore={false}
          overlay={loginWall}
          footer={
            <div className="ledger-foot">
              <p><i className="signal scored"></i><b>Scored</b> means a judge result exists.</p>
              <p><i className="signal unscored"></i><b>Unscored</b> is a distinct state, not a certification claim.</p>
              <a href={`#/ask?q=${encodeURIComponent(query.trim())}`}>Ask from these sources <span aria-hidden="true">→</span></a>
            </div>
          }
        />
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
          <article><code>01 / SEARCH</code><p>Query the frozen corpus. Every hit returns its URL, capture date, domain, and authenticity state.</p><span>cryo_search</span></article>
          <article><code>02 / READ</code><p>Pull full page text by id or URL. Missing pages are fetched live from pre-2022 Wayback snapshots and frozen in.</p><span>cryo_get_page</span></article>
          <article><code>03 / BROWSE</code><p>Enumerate a domain's captured archive to walk an era of a site, not just one page.</p><span>cryo_list_domain</span></article>
          <article><code>04 / ASK</code><p>Grounded synthesis citing only frozen snapshots — every claim traces back to a ledger entry.</p><span>cryo_answer</span></article>
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
            <div><dt>SDK</dt><dd>Typed Python client (cryo-search) with retries and the full ledger — beta, on GitHub</dd></div>
            <div><dt>Agents</dt><dd>CryoSearchTool + CryoAnswerTool for LangChain / LlamaIndex</dd></div>
            <div><dt>MCP</dt><dd>Five native tools for Claude Code &amp; Desktop at /mcp</dd></div>
          </dl>
          <a href="#/docs">Open the docs <span aria-hidden="true">→</span></a>
        </article>
      </section>
    </>
  );
}
