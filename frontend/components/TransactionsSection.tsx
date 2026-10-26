"use client";

// The "Transactions" part of the results: status filter, search, category filter and the table.
// The filters only change what is shown; they never change any data.

import { useState } from "react";
import { CategorySelect } from "./CategorySelect";
import { StatusBar } from "./StatusBar";
import { TxTable } from "./TxTable";
import { filterRows, sortRows } from "@/lib/format";
import type { Category, Row } from "@/lib/types";

interface Props {
  rows: Row[];
  categories: Category[];
  saving: boolean;
  onCategoryChange: (row: Row, category: string) => void;
  onBusinessPctChange: (row: Row, pct: number) => void;
}

export function TransactionsSection({ rows, categories, saving, onCategoryChange, onBusinessPctChange }: Props) {
  // "all" means that filter is off.
  const [statusFilter, setStatusFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [search, setSearch] = useState("");

  const visibleRows = sortRows(filterRows(rows, statusFilter, categoryFilter, search));
  const filtersOn = statusFilter !== "all" || categoryFilter !== "all" || search !== "";

  function clearFilters() {
    setStatusFilter("all");
    setCategoryFilter("all");
    setSearch("");
  }

  return (
    <section aria-labelledby="transactions-heading" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="transactions-heading" className="text-lg font-semibold text-slate-900">
          Transactions
        </h2>
        <StatusBar rows={rows} active={statusFilter} onSelect={setStatusFilter} />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search descriptions…"
          aria-label="Search descriptions"
          className="min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
        <div className="w-52">
          <CategorySelect
            label="Filter by category"
            categories={categories}
            value={categoryFilter === "all" ? null : categoryFilter}
            placeholder="All categories"
            onChange={setCategoryFilter}
          />
        </div>
        {filtersOn && (
          <button type="button" onClick={clearFilters} className="text-sm font-medium text-indigo-600 hover:underline">
            Clear filters
          </button>
        )}
      </div>

      <p className="sr-only" aria-live="polite">
        Showing {visibleRows.length} of {rows.length} rows
      </p>

      <TxTable
        rows={visibleRows}
        categories={categories}
        saving={saving}
        onCategoryChange={onCategoryChange}
        onBusinessPctChange={onBusinessPctChange}
      />
    </section>
  );
}
