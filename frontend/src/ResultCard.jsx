/**
 * ResultCard — premium glass result card.
 */

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

const CONTENT_TYPE_COLORS = {
  article:      "text-[#4a9eff]/80",
  encyclopedia: "text-purple-400/80",
  qa:           "text-emerald-400/80",
  discussion:   "text-orange-400/80",
  blog:         "text-teal-400/80",
  book:         "text-amber-400/80",
};

function formatTimestamp(ts) {
  if (!ts || ts.length < 6) return ts || "";
  const year = ts.slice(0, 4);
  const month = parseInt(ts.slice(4, 6), 10);
  return `${MONTHS[month - 1] || "?"} ${year}`;
}

function parseBreadcrumb(url) {
  if (!url) return { domain: "", segments: [] };
  try {
    const u = new URL(url);
    const pathParts = u.pathname.split("/").filter(Boolean).slice(0, 3);
    return { domain: u.hostname, segments: pathParts };
  } catch {
    return { domain: url, segments: [] };
  }
}

function safeHighlight(html) {
  if (!html) return "";
  return html.replace(/<(?!\/?mark\b)[^>]+>/gi, "");
}

function HumanScoreBar({ score }) {
  if (score === null || score === undefined) return null;
  const pct = Math.round(score * 100);
  const hue = Math.round(score * 120);
  return (
    <div className="flex items-center gap-2 mt-3">
      <div className="flex-1 h-px bg-white/5 relative overflow-hidden rounded-full">
        <div
          className="absolute left-0 top-0 h-full transition-all duration-300 rounded-full"
          style={{ width: `${pct}%`, backgroundColor: `hsl(${hue}, 65%, 50%)` }}
        />
      </div>
      <span className="text-[10px] text-white/25 w-8 text-right" style={{ fontFamily: 'var(--font-mono)' }}>
        {pct}%
      </span>
    </div>
  );
}

export default function ResultCard({ result }) {
  const {
    url,
    text_preview,
    timestamp,
    word_count,
    content_type,
    human_score,
    cryo_certified,
  } = result;

  const { domain, segments } = parseBreadcrumb(url);
  const readingTime = word_count ? Math.max(1, Math.ceil(word_count / 200)) : null;
  const typeColor = CONTENT_TYPE_COLORS[content_type] || "text-white/30";
  const highlightedPreview = safeHighlight(text_preview);

  return (
    <article className="liquid-glass rounded-xl px-5 py-4 mb-3 hover:bg-white/[0.04] transition-all duration-150">

      {/* URL breadcrumb */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-white/25 hover:text-white/50 transition-colors truncate flex-1 font-light"
          style={{ fontFamily: 'var(--font-mono)' }}
          title={url}
        >
          <span className="text-[#4a9eff]/70">{domain}</span>
          {segments.map((seg, i) => (
            <span key={i}>
              <span className="mx-1 text-white/15">›</span>
              <span>{decodeURIComponent(seg)}</span>
            </span>
          ))}
        </a>

        <div className="flex items-center gap-2 shrink-0">
          {cryo_certified && (
            <span className="text-[10px] text-emerald-400/60 font-light">
              ✓ verified
            </span>
          )}
          <a
            href={`https://web.archive.org/web/*/${url}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[10px] text-white/20 hover:text-[#4a9eff]/60 transition-colors font-light"
            title="View in Wayback Machine"
          >
            ⏱ Wayback
          </a>
        </div>
      </div>

      {/* Text preview */}
      <div
        className="text-sm text-white/60 leading-relaxed line-clamp-3 mb-3 font-light"
        dangerouslySetInnerHTML={{ __html: highlightedPreview || "—" }}
      />

      {/* Metadata */}
      <div className="flex flex-wrap items-center gap-3 text-[11px] text-white/20 font-light">
        {timestamp && (
          <span>{formatTimestamp(timestamp)}</span>
        )}
        {content_type && (
          <span className={typeColor}>{content_type}</span>
        )}
        {word_count && (
          <span>{word_count.toLocaleString()} words</span>
        )}
        {readingTime && (
          <span>~{readingTime} min</span>
        )}
      </div>

      {human_score !== null && human_score !== undefined && (
        <HumanScoreBar score={human_score} />
      )}
    </article>
  );
}
