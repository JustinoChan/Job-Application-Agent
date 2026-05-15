import { useEffect, useState } from "react";

export interface FilterState {
  minFit: number;
  company: string;
  search: string;
}

interface FilterBarProps {
  value: FilterState;
  onChange: (next: FilterState) => void;
}

export default function FilterBar({ value, onChange }: FilterBarProps) {
  const [search, setSearch] = useState(value.search);

  useEffect(() => {
    const t = window.setTimeout(() => {
      if (search !== value.search) {
        onChange({ ...value, search });
      }
    }, 350);
    return () => window.clearTimeout(t);
  }, [search]);

  return (
    <div className="filter-bar">
      <label className="filter-field">
        <span>Min fit</span>
        <input
          type="range"
          min={0}
          max={100}
          step={5}
          value={Math.round(value.minFit * 100)}
          onChange={(e) => onChange({ ...value, minFit: Number(e.target.value) / 100 })}
        />
        <span className="filter-value">{Math.round(value.minFit * 100)}%</span>
      </label>
      <label className="filter-field">
        <span>Company</span>
        <input
          type="text"
          value={value.company}
          placeholder="filter by name"
          onChange={(e) => onChange({ ...value, company: e.target.value })}
        />
      </label>
      <label className="filter-field">
        <span>Search posting text</span>
        <input
          type="search"
          value={search}
          placeholder="keyword, framework, technology..."
          onChange={(e) => setSearch(e.target.value)}
        />
      </label>
      {(value.minFit > 0 || value.company || value.search) && (
        <button
          type="button"
          className="filter-reset"
          onClick={() => {
            setSearch("");
            onChange({ minFit: 0, company: "", search: "" });
          }}
        >
          Reset
        </button>
      )}
    </div>
  );
}
