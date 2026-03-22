/**
 * AutocompleteInput — liquid glass search bar with suggestion dropdown.
 */

import { useEffect, useRef, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "";

export default function AutocompleteInput({ value, onChange, onSearch, inputRef: externalRef }) {
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const suggestTimerRef = useRef(null);
  const containerRef = useRef(null);
  const localRef = useRef(null);
  const inputEl = externalRef || localRef;

  useEffect(() => {
    if (!value || value.length < 2) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
    clearTimeout(suggestTimerRef.current);
    suggestTimerRef.current = setTimeout(async () => {
      try {
        const res = await fetch(`${API_URL}/suggest?q=${encodeURIComponent(value)}`);
        if (res.ok) {
          const data = await res.json();
          setSuggestions(data);
          setOpen(data.length > 0);
          setActiveIndex(-1);
        }
      } catch {
        setSuggestions([]);
        setOpen(false);
      }
    }, 150);
    return () => clearTimeout(suggestTimerRef.current);
  }, [value]);

  useEffect(() => {
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  function handleKeyDown(e) {
    if (!open || suggestions.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, -1));
    } else if (e.key === "Enter" && activeIndex >= 0) {
      e.preventDefault();
      selectSuggestion(suggestions[activeIndex]);
    } else if (e.key === "Escape") {
      setOpen(false);
      setActiveIndex(-1);
    }
  }

  function selectSuggestion(suggestion) {
    onChange(suggestion);
    setOpen(false);
    setActiveIndex(-1);
    onSearch(suggestion);
  }

  return (
    <div ref={containerRef} className="relative w-full">
      <div className="relative liquid-glass-strong rounded-2xl">
        <input
          ref={inputEl}
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setOpen(true)}
          placeholder="Search the human web..."
          autoComplete="off"
          spellCheck="false"
          className="w-full bg-transparent text-white placeholder-white/25
                     px-6 py-4 text-base focus:outline-none rounded-2xl
                     font-light tracking-wide"
          style={{ fontFamily: 'var(--font-body)' }}
        />
        {value && (
          <button
            onClick={() => { onChange(""); setSuggestions([]); setOpen(false); inputEl.current?.focus(); }}
            className="absolute right-5 top-1/2 -translate-y-1/2 text-white/30
                       hover:text-white/70 text-xl leading-none transition-colors"
            aria-label="Clear search"
          >
            ×
          </button>
        )}
      </div>

      {open && suggestions.length > 0 && (
        <ul
          className="absolute z-50 w-full mt-2 liquid-glass-strong rounded-xl overflow-hidden shadow-2xl"
          role="listbox"
        >
          {suggestions.map((s, i) => (
            <li
              key={s}
              role="option"
              aria-selected={i === activeIndex}
              onMouseDown={() => selectSuggestion(s)}
              onMouseEnter={() => setActiveIndex(i)}
              className={`px-5 py-2.5 text-sm cursor-pointer transition-colors font-light ${
                i === activeIndex
                  ? "bg-white/10 text-white"
                  : "text-white/50 hover:bg-white/5 hover:text-white/80"
              }`}
            >
              <span className="mr-2 text-white/20">↗</span>
              {s}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
