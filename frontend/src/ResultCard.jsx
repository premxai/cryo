/**
 * ResultCard — a single row in the archive result ledger.
 * Three columns: source (number + title + snippet + url), capture, authenticity.
 */

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function formatCapture(ts) {
  if (!ts || ts.length < 8) return ts || "";
  const year = ts.slice(0, 4);
  const month = parseInt(ts.slice(4, 6), 10);
  const day = ts.slice(6, 8);
  return `${year}-${String(month).padStart(2, "0")}-${day}`;
}

function shortMonth(ts) {
  if (!ts || ts.length < 6) return "";
  const year = ts.slice(0, 4);
  const month = parseInt(ts.slice(4, 6), 10);
  return `${MONTHS[month - 1] || "?"} ${year}`;
}

function domainOf(url) {
  if (!url) return "";
  try { return new URL(url).hostname.replace(/^www\./, ""); }
  catch { return url; }
}

/** Keep only <mark> tags from the highlighted preview; strip everything else. */
function safeHighlight(html) {
  if (!html) return "";
  return html.replace(/<(?!\/?mark\b)[^>]+>/gi, "");
}

export default function ResultCard({ result, index }) {
  const { url, text_preview, timestamp, content_type, human_score } = result;
  const domain = domainOf(url);
  const preview = safeHighlight(text_preview);
  const scored = human_score !== null && human_score !== undefined;

  return (
    <article className="result">
      <div className="result-main">
        <span className="result-number">{String((index ?? 0) + 1).padStart(2, "0")}</span>
        <div>
          <a href={url} target="_blank" rel="noreferrer">
            {domain}{content_type ? ` · ${content_type}` : ""}
          </a>
          <p dangerouslySetInnerHTML={{ __html: preview || "—" }} />
          <span className="result-url">{url}</span>
        </div>
      </div>
      <span className="result-meta">
        {shortMonth(timestamp)}<br />
        <a
          href={`https://web.archive.org/web/*/${url}`}
          target="_blank"
          rel="noreferrer"
          style={{ color: "var(--muted)" }}
        >
          archive available
        </a>
      </span>
      <span className={`score${scored ? "" : " unscored"}`}>
        {scored
          ? <>HUMAN {human_score.toFixed(2)}<br />SCORED</>
          : <>UNSCORED<br />NO JUDGE RESULT</>}
      </span>
    </article>
  );
}
