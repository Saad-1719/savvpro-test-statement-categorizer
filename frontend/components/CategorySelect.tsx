"use client";

import { kindLabel } from "@/lib/format";
import type { Category } from "@/lib/types";

interface Props {
  categories: Category[];
  value: string | null;
  onChange: (category: string) => void;
  disabled?: boolean;
  placeholder?: string;
  label: string;
}

/** Category dropdown grouped by kind; the list always comes from GET /api/categories. */
export function CategorySelect({ categories, value, onChange, disabled, placeholder = "Choose…", label }: Props) {
  const kinds = Array.from(new Set(categories.map((c) => c.kind)));
  return (
    <select
      aria-label={label}
      value={value ?? ""}
      disabled={disabled}
      onChange={(e) => e.target.value && onChange(e.target.value)}
      className="w-full min-w-[9rem] rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-slate-50 disabled:text-slate-400"
    >
      <option value="" disabled>
        {placeholder}
      </option>
      {kinds.map((kind) => (
        <optgroup key={kind} label={kindLabel(kind)}>
          {categories
            .filter((c) => c.kind === kind)
            .map((c) => (
              <option key={c.name} value={c.name}>
                {c.name}
              </option>
            ))}
        </optgroup>
      ))}
    </select>
  );
}
