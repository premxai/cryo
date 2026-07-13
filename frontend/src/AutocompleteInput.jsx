/**
 * AutocompleteInput — hero-search bar with an archive suggestion dropdown.
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
    <form
      ref={containerRef}
      className="hero-search"
      onSubmit={(e) => { e.preventDefault(); setOpen(false); onSearch(value); }}
    >
      <label className="sr-only" htmlFor="hero-query">Search the frozen human web</label>
      <input
        id="hero-query"
        ref={inputEl}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={() => suggestions.length > 0 && setOpen(true)}
        placeholder="Search the frozen human web…"
        autoComplete="off"
        spellCheck="false"
      />
      <button type="submit">Search <span aria-hidden="true">→</span></button>

      {open && suggestions.length > 0 && (
        <ul className="suggest-list" role="listbox">
          {suggestions.map((s, i) => (
            <li
              key={s}
              role="option"
              aria-selected={i === activeIndex}
              onMouseDown={() => selectSuggestion(s)}
              onMouseEnter={() => setActiveIndex(i)}
            >
              <span aria-hidden="true">↗</span>{s}
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}
