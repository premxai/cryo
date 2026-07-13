/**
 * FilterSidebar — archive-editorial filter block.
 * Sort, year range, content type, and top-domain facets rendered as ruled
 * mono controls inside the search-intro column.
 */

const CONTENT_TYPES = [
  { value: "", label: "All records" },
  { value: "article", label: "Article" },
  { value: "encyclopedia", label: "Encyclopedia" },
  { value: "qa", label: "Q&A" },
  { value: "discussion", label: "Discussion" },
  { value: "blog", label: "Blog" },
];

const SORT_OPTIONS = [
  { value: "relevance", label: "Relevant" },
  { value: "date_desc", label: "Newest" },
  { value: "date_asc", label: "Oldest" },
];

export default function FilterSidebar({ filters, facets, onFilterChange, onSortChange, sort }) {
  function update(key, value) {
    onFilterChange({ ...filters, [key]: value });
  }

  const domainFacets = facets?.domain?.slice(0, 6) || [];
  const hasActiveFilters =
    filters.yearMin !== 2000 ||
    filters.yearMax !== 2021 ||
    filters.domain ||
    filters.contentType ||
    sort !== "relevance";

  return (
    <div className="filter-block" aria-label="Search filters">
      <div className="filter-label">Sort by</div>
      <div className="filter-group">
        {SORT_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            className={`filter${sort === opt.value ? " is-active" : ""}`}
            aria-pressed={sort === opt.value}
            onClick={() => onSortChange(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <div className="filter-label">Record class</div>
      <div className="filter-group">
        {CONTENT_TYPES.map((ct) => (
          <button
            key={ct.value}
            type="button"
            className={`filter${filters.contentType === ct.value ? " is-active" : ""}`}
            aria-pressed={filters.contentType === ct.value}
            onClick={() => update("contentType", ct.value)}
          >
            {ct.label}
          </button>
        ))}
      </div>

      <div className="filter-label">Captured between</div>
      <div className="year-range">
        <input
          type="number"
          min={2000}
          max={2021}
          value={filters.yearMin}
          onChange={(e) => update("yearMin", parseInt(e.target.value) || 2000)}
          aria-label="Earliest year"
        />
        <span>—</span>
        <input
          type="number"
          min={2000}
          max={2021}
          value={filters.yearMax}
          onChange={(e) => update("yearMax", parseInt(e.target.value) || 2021)}
          aria-label="Latest year"
        />
      </div>

      {domainFacets.length > 0 && (
        <>
          <div className="filter-label">Top sources</div>
          <div className="filter-group">
            <button
              type="button"
              className={`filter${!filters.domain ? " is-active" : ""}`}
              aria-pressed={!filters.domain}
              onClick={() => update("domain", "")}
            >
              All
            </button>
            {domainFacets.map((f) => (
              <button
                key={f.value}
                type="button"
                className={`filter${filters.domain === f.value ? " is-active" : ""}`}
                aria-pressed={filters.domain === f.value}
                onClick={() => update("domain", filters.domain === f.value ? "" : f.value)}
                title={`${f.value} · ${f.count}`}
              >
                {f.value} {f.count}
              </button>
            ))}
          </div>
        </>
      )}

      {hasActiveFilters && (
        <div className="filter-label" style={{ marginTop: "1.6rem" }}>
          <button
            type="button"
            className="filter"
            onClick={() => { onFilterChange({ yearMin: 2000, yearMax: 2021, domain: "", contentType: "" }); onSortChange("relevance"); }}
          >
            Clear all filters
          </button>
        </div>
      )}
    </div>
  );
}
