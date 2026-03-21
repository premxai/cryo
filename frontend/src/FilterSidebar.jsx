/**
 * FilterSidebar — collapsible filter panel with year range, domain, content type.
 * Emits changes via onFilterChange({ yearMin, yearMax, domain, contentType }).
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
    <aside className="w-56 shrink-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-2 text-xs text-[#4a5568] hover:text-[#a0aec0] transition-colors"
        >
          <span>{collapsed ? "▶" : "▼"}</span>
          <span className="uppercase tracking-widest">Filters</span>
        </button>
        {hasActiveFilters && (
          <button
            onClick={() => onFilterChange({ yearMin: 2000, yearMax: 2021, domain: "", contentType: "" })}
            className="text-xs text-[#4a9eff] hover:underline"
          >
            Clear
          </button>
        )}
      </div>

      {!collapsed && (
        <div className="space-y-6">
          {/* Sort */}
          <div>
            <div className="text-xs text-[#4a5568] uppercase tracking-widest mb-2">Sort By</div>
            <div className="space-y-1">
              {SORT_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => onSortChange(opt.value)}
                  className={`w-full text-left text-sm px-2 py-1 transition-colors ${
                    sort === opt.value
                      ? "text-[#4a9eff] bg-[#0d1525]"
                      : "text-[#a0aec0] hover:text-[#e8edf5]"
                  }`}
                >
                  {sort === opt.value && <span className="mr-1">›</span>}
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Year range */}
          <div>
            <div className="text-xs text-[#4a5568] uppercase tracking-widest mb-2">Year Range</div>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={2000}
                max={2021}
                value={filters.yearMin}
                onChange={(e) => update("yearMin", parseInt(e.target.value) || 2000)}
                className="w-20 bg-[#0d1525] border border-[#1e2d45] text-[#e8edf5] text-sm
                           px-2 py-1 focus:outline-none focus:border-[#4a9eff]"
              />
              <span className="text-[#4a5568] text-xs">–</span>
              <input
                type="number"
                min={2000}
                max={2021}
                value={filters.yearMax}
                onChange={(e) => update("yearMax", parseInt(e.target.value) || 2021)}
                className="w-20 bg-[#0d1525] border border-[#1e2d45] text-[#e8edf5] text-sm
                           px-2 py-1 focus:outline-none focus:border-[#4a9eff]"
              />
            </div>
          </div>

          {/* Content type */}
          <div>
            <div className="text-xs text-[#4a5568] uppercase tracking-widest mb-2">Content Type</div>
            <div className="space-y-1">
              {CONTENT_TYPES.map((ct) => (
                <button
                  key={ct.value}
                  onClick={() => update("contentType", ct.value)}
                  className={`w-full text-left text-sm px-2 py-1 transition-colors ${
                    filters.contentType === ct.value
                      ? "text-[#4a9eff]"
                      : "text-[#a0aec0] hover:text-[#e8edf5]"
                  }`}
                >
                  {filters.contentType === ct.value && <span className="mr-1">›</span>}
                  {ct.label}
                </button>
              ))}
            </div>
          </div>

          {/* Top domains */}
          {domainFacets.length > 0 && (
            <div>
              <div className="text-xs text-[#4a5568] uppercase tracking-widest mb-2">Top Sources</div>
              <div className="space-y-1">
                <button
                  onClick={() => update("domain", "")}
                  className={`w-full text-left text-sm px-2 py-1 transition-colors ${
                    !filters.domain ? "text-[#4a9eff]" : "text-[#a0aec0] hover:text-[#e8edf5]"
                  }`}
                >
                  All sources
                </button>
                {domainFacets.map((f) => (
                  <button
                    key={f.value}
                    onClick={() => update("domain", filters.domain === f.value ? "" : f.value)}
                    className={`w-full text-left text-sm px-2 py-1 flex justify-between items-center
                                transition-colors ${
                      filters.domain === f.value
                        ? "text-[#4a9eff]"
                        : "text-[#a0aec0] hover:text-[#e8edf5]"
                    }`}
                  >
                    <span className="truncate max-w-[130px]">{f.value}</span>
                    <span className="text-[#4a5568] text-xs ml-1">{f.count}</span>
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
