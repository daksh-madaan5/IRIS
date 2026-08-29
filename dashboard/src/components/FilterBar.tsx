import { Filter, Search, X } from "lucide-react";
import type { DashboardFilters, DashboardOptions } from "../types";

interface FilterBarProps {
  filters: DashboardFilters;
  options: DashboardOptions;
  onChange: (next: DashboardFilters) => void;
  onReset: () => void;
}

const fields: Array<{
  key: "sector" | "agency" | "ministry" | "state";
  label: string;
  options: "sectors" | "agencies" | "ministries" | "states";
}> = [
  { key: "sector", label: "Sector", options: "sectors" },
  { key: "agency", label: "Agency", options: "agencies" },
  { key: "ministry", label: "Ministry", options: "ministries" },
  { key: "state", label: "State", options: "states" },
];

export function FilterBar({ filters, options, onChange, onReset }: FilterBarProps) {
  const hasFilters = Object.values(filters).some(Boolean);
  return (
    <section className="filter-panel" aria-label="Portfolio filters">
      <div className="filter-title">
        <Filter size={16} aria-hidden="true" />
        <span>Portfolio filters</span>
      </div>
      <label className="search-field">
        <span className="sr-only">Search by project code or name</span>
        <Search size={17} aria-hidden="true" />
        <input
          value={filters.search}
          onChange={(event) => onChange({ ...filters, search: event.target.value })}
          placeholder="Search project code or name"
        />
      </label>
      {fields.map((field) => (
        <label className="select-field" key={field.key}>
          <span>{field.label}</span>
          <select
            aria-label={field.label}
            value={filters[field.key]}
            onChange={(event) => onChange({ ...filters, [field.key]: event.target.value })}
          >
            <option value="">All {field.label.toLowerCase()}s</option>
            {options[field.options].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      ))}
      {hasFilters && (
        <button className="reset-button" type="button" onClick={onReset}>
          <X size={15} aria-hidden="true" /> Clear
        </button>
      )}
    </section>
  );
}
