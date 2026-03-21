/**
 * ResultCard — upgraded search result card.
 *
 * M1.5 additions:
 *   - Highlighted matched terms (<mark> tags from Meilisearch)
 *   - Breadcrumb-style URL (domain › path › segments)
 *   - Content-type badge (color-coded)
 *   - Metadata footer: timestamp, reading time, word count
 *
 * M2 additions (wired but hidden until score arrives):
 *   - Human score bar
 *   - Cryo Certified badge
 */

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

const CONTENT_TYPE_COLORS = {
  article: "text-[#4a9eff] border-[#4a9eff]/30",
  encyclopedia: "text-purple-400 border-purple-400/30",
  qa: "text-green-400 border-green-400/30",
  discussion: "text-orange-400 border-orange-400/30",
  blog: "text-teal-400 border-teal-400/30",
};

function formatTimestamp(ts) {
  if (!ts || ts.length < 6) return ts || "unknown";
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

/** Sanitize HTML — keep only <mark> tags, strip everything else. */
function safeHighlight(html) {
  if (!html) return "";
  return html.replace(/<(?!\/?mark\b)[^>]+>/gi, "");
}

function HumanScoreBar({ score }) {
  if (score === null || score === undefined) return null;
  const pct = Math.round(score * 100);
  const hue = Math.round(score * 120);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-0.5 bg-[#1e2d45] relative overflow-hidden">
        <div
          className="absolute left-0 top-0 h-full transition-all duration-300"
          style={{ width: `${pct}%`, backgroundColor: `hsl(${hue}, 65%, 45%)` }}
        />
      </div>
      <span className="font-mono text-[10px] text-[#4a5568] w-8 text-right">{pct}%</span>
    </div>
  );
}

export default function ResultCard({ result }) {
  const {
    url,
    text_preview,
    timestamp,
    domain,
    word_count,
    content_type,
    human_score,
    cryo_certified,
  } = result;

  const { domain: parsedDomain, segments } = parseBreadcrumb(url);
  const readingTime = word_count ? Math.max(1, Math.ceil(word_count / 200)) : null;
  const typeColor = CONTENT_TYPE_COLORS[content_type] || "text-[#4a5568] border-[#4a5568]/30";
  const highlightedPreview = safeHighlight(text_preview);

  return (
    <article className="border-b border-[#1e2d45] py-5 group hover:bg-[#0c1420] transition-colors duration-100 -mx-2 px-2">

      {/* Breadcrumb URL */}
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-[#4a5568] hover:text-[#a0aec0] transition-colors font-mono truncate flex-1"
          title={url}
        >
          <span className="text-[#4a9eff]">{parsedDomain}</span>
          {segments.map((seg, i) => (
            <span key={i}>
              <span className="mx-1 text-[#2d3a4a]">›</span>
              <span className="text-[#4a5568]">{decodeURIComponent(seg)}</span>
            </span>
          ))}
        </a>

        <div className="flex items-center gap-2 flex-shrink-0">
          {cryo_certified && (
            <span className="font-mono text-[10px] text-green-400/70 border border-green-400/25 px-1.5 py-0.5 whitespace-nowrap">
              ✓ Cryo
            </span>
          )}
          <a
            href={`https://web.archive.org/web/*/${url}`}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-[10px] text-[#4a5568] hover:text-[#4a9eff] transition-colors whitespace-nowrap"
            title="View in Wayback Machine"
          >
            ⏱ Wayback
          </a>
        </div>
      </div>

      {/* Text preview with highlighting */}
      <div
        className="text-sm text-[#a0aec0] leading-relaxed line-clamp-3 mb-3"
        dangerouslySetInnerHTML={{ __html: highlightedPreview || "—" }}
        style={{ "--mark-bg": "transparent", "--mark-color": "#4a9eff" }}
      />

      {/* Metadata footer */}
      <div className="flex flex-wrap items-center gap-3 text-[10px] font-mono">
        {/* Timestamp */}
        <span className="text-[#4a5568] border border-[#1e2d45] px-1.5 py-0.5">
          {formatTimestamp(timestamp)}
        </span>

        {/* Content type badge */}
        {content_type && (
          <span className={`border px-1.5 py-0.5 ${typeColor}`}>
            {content_type}
          </span>
        )}

        {/* Word count */}
        {word_count && (
          <span className="text-[#2d3a4a]">{word_count.toLocaleString()} words</span>
        )}

        {/* Reading time */}
        {readingTime && (
          <span className="text-[#2d3a4a]">~{readingTime} min read</span>
        )}
      </div>

      {/* Human score bar (M2 — hidden until score arrives) */}
      {human_score !== null && human_score !== undefined && (
        <div className="mt-3 pt-2 border-t border-[#1a2535]">
          <div className="flex items-center justify-between mb-1">
            <span className="font-mono text-[10px] text-[#2d3a4a]">authenticity</span>
          </div>
          <HumanScoreBar score={human_score} />
        </div>
      )}
    </article>
  );
}
