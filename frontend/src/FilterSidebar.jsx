/**
 * FilterSidebar — glass filter panel.
 */

import { useState } from "react";

const CONTENT_TYPES = [
  { value: "", label: "All types" },
  { value: "article", label: "Article" },
  { value: "encyclopedia", label: "Encyclopedia" },
  { value: "qa", label: "Q&A" },
  { value: "discussion", label: "Discussion" },
  { value: "blog", label: "Blog" },
];

const SORT_OPTIONS = [
  { value: "relevance", label: "Most Relevant" },
  { value: "date_desc", label: "Newest First" },
  { value: "date_asc", label: "Oldest First" },
];

export default function FilterSidebar({ filters, facets, onFilterChange, onSortChange, sort }) {
  const [collapsed, setCollapsed] = useState(false);

  function update(key, value) {
    onFilterChange({ ...filters, [key]: value });
  }

  const domainFacets = facets?.domain?.slice(0, 10) || [];
  const hasActiveFilters =
    filters.yearMin !== 2000 ||
    filters.yearMax !== 2021 ||
    filters.domain ||
    filters.contentType;

  return (
    <aside className="w-52 shrink-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-2 text-xs text-white/25 hover:text-white/50 transition-colors font-light tracking-widest uppercase"
        >
          <span className="text-[10px]">{collapsed ? "▶" : "▼"}</span>
          Filters
        </button>
        {hasActiveFilters && (
          <button
            onClick={() => onFilterChange({ yearMin: 2000, yearMax: 2021, domain: "", contentType: "" })}
            className="text-xs text-[#4a9eff]/60 hover:text-[#4a9eff] transition-colors font-light"
          >
            Clear
          </button>
        )}
      </div>

      {!collapsed && (
        <div className="space-y-6">

          {/* Sort */}
          <div>
            <div className="text-[10px] text-white/20 uppercase tracking-widest mb-2 font-light">Sort By</div>
            <div className="space-y-0.5">
              {SORT_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => onSortChange(opt.value)}
                  className={`w-full text-left text-sm px-2 py-1.5 rounded-lg transition-colors font-light ${
                    sort === opt.value
                      ? "text-white/80 bg-white/5"
                      : "text-white/30 hover:text-white/60"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Year range */}
          <div>
            <div className="text-[10px] text-white/20 uppercase tracking-widest mb-2 font-light">Year Range</div>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={2000}
                max={2021}
                value={filters.yearMin}
                onChange={(e) => update("yearMin", parseInt(e.target.value) || 2000)}
                className="w-20 bg-white/5 text-white/60 text-sm rounded-lg
                           px-2 py-1.5 focus:outline-none focus:bg-white/8
                           border-none font-light"
              />
              <span className="text-white/20 text-xs">–</span>
              <input
                type="number"
                min={2000}
                max={2021}
                value={filters.yearMax}
                onChange={(e) => update("yearMax", parseInt(e.target.value) || 2021)}
                className="w-20 bg-white/5 text-white/60 text-sm rounded-lg
                           px-2 py-1.5 focus:outline-none focus:bg-white/8
                           border-none font-light"
              />
            </div>
          </div>

          {/* Content type */}
          <div>
            <div className="text-[10px] text-white/20 uppercase tracking-widest mb-2 font-light">Content Type</div>
            <div className="space-y-0.5">
              {CONTENT_TYPES.map((ct) => (
                <button
                  key={ct.value}
                  onClick={() => update("contentType", ct.value)}
                  className={`w-full text-left text-sm px-2 py-1.5 rounded-lg transition-colors font-light ${
                    filters.contentType === ct.value
                      ? "text-white/80 bg-white/5"
                      : "text-white/30 hover:text-white/60"
                  }`}
                >
                  {ct.label}
                </button>
              ))}
            </div>
          </div>

          {/* Top domains */}
          {domainFacets.length > 0 && (
            <div>
              <div className="text-[10px] text-white/20 uppercase tracking-widest mb-2 font-light">Top Sources</div>
              <div className="space-y-0.5">
                <button
                  onClick={() => update("domain", "")}
                  className={`w-full text-left text-sm px-2 py-1.5 rounded-lg transition-colors font-light ${
                    !filters.domain ? "text-white/80 bg-white/5" : "text-white/30 hover:text-white/60"
                  }`}
                >
                  All sources
                </button>
                {domainFacets.map((f) => (
                  <button
                    key={f.value}
                    onClick={() => update("domain", filters.domain === f.value ? "" : f.value)}
                    className={`w-full text-left text-sm px-2 py-1.5 rounded-lg flex justify-between items-center
                                transition-colors font-light ${
                      filters.domain === f.value
                        ? "text-white/80 bg-white/5"
                        : "text-white/30 hover:text-white/60"
                    }`}
                  >
                    <span className="truncate max-w-[120px]">{f.value}</span>
                    <span className="text-white/20 text-xs ml-1">{f.count}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

        </div>
      )}
    </aside>
  );
}
