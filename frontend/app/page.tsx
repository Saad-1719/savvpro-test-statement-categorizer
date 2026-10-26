"use client";

// The whole app is this one page:
//   1. Before upload: show the upload box.
//   2. After upload: show the file summary, the Needs Review queue, the table of rows and the totals.
// Every time the user changes something, we send it to the backend and then reload the data,
// so the screen always shows what the backend decided.

import { useEffect, useState } from "react";
import { CategorySelect } from "@/components/CategorySelect";
import { FileSummaryCard } from "@/components/FileSummaryCard";
import { ReviewQueue, type GroupFix } from "@/components/ReviewQueue";
import { StatusBar } from "@/components/StatusBar";
import { SummaryCards } from "@/components/SummaryCards";
import { CheckIcon, LogoIcon } from "@/components/icons";
import { Totals } from "@/components/Totals";
import { TxTable } from "@/components/TxTable";
import { UploadZone } from "@/components/UploadZone";
import {
  ApiError,
  exportUrl,
  getCategories,
  getReviewGroups,
  getSummary,
  getTransactions,
  saveAlwaysRule,
  updateTransaction,
  uploadStatement,
} from "@/lib/api";
import { filterRows, sortRows } from "@/lib/format";
import type { Category, ReviewGroup, Row, Session, Summary } from "@/lib/types";

// Turns any error into a message we can show.
function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

export default function Home() {
  // Data from the backend
  const [categories, setCategories] = useState<Category[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [reviewGroups, setReviewGroups] = useState<ReviewGroup[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);

  // Screen state
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Table filters ("all" means no filter)
  const [statusFilter, setStatusFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [search, setSearch] = useState("");

  // Load the category list once, for the dropdowns.
  useEffect(() => {
    getCategories()
      .then(setCategories)
      .catch((e) => setError(errorMessage(e)));
  }, []);

  // Reloads rows, review groups and totals from the backend.
  async function reload(sessionId: string) {
    setRows(await getTransactions(sessionId));
    setReviewGroups(await getReviewGroups(sessionId));
    setSummary(await getSummary(sessionId));
  }

  async function handleUpload(file: File, taxYear?: number) {
    setUploading(true);
    setError(null);
    setNotice(null);
    try {
      const newSession = await uploadStatement(file, taxYear);
      setSession(newSession);
      clearFilters();
      await reload(newSession.session_id);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setUploading(false);
    }
  }

  // Runs one change against the backend, then reloads so the screen matches.
  async function saveAndReload(change: (sessionId: string) => Promise<void>) {
    if (!session) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await change(session.session_id);
      await reload(session.session_id);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  function changeCategory(row: Row, category: string) {
    saveAndReload(async (sessionId) => {
      await updateTransaction(sessionId, row.id, { category: category });
    });
  }

  function changeBusinessPct(row: Row, pct: number) {
    if (pct < 0 || pct > 100) {
      setError("Business-use % must be between 0 and 100.");
      return;
    }
    saveAndReload(async (sessionId) => {
      await updateTransaction(sessionId, row.id, { business_pct: pct });
    });
  }

  // Applies one category to every row in a Needs Review group.
  function fixReviewGroup(group: ReviewGroup, fix: GroupFix) {
    saveAndReload(async (sessionId) => {
      if (fix.always) {
        // Save a rule. The backend applies it to all rows from this merchant, now and in later uploads.
        const result = await saveAlwaysRule(sessionId, group.merchant_key, fix.category);
        setNotice(`Saved rule: always ${result.rule.merchant_key} as ${result.rule.category} (${result.updated_count} rows updated).`);
      } else {
        for (const id of group.transaction_ids) {
          await updateTransaction(sessionId, id, { category: fix.category });
        }
      }

      // Mixed-use categories like Phone & Data also need the business-use %.
      if (fix.businessPct !== undefined) {
        for (const id of group.transaction_ids) {
          await updateTransaction(sessionId, id, { business_pct: fix.businessPct });
        }
      }
    });
  }

  function clearFilters() {
    setStatusFilter("all");
    setCategoryFilter("all");
    setSearch("");
  }

  function startOver() {
    setSession(null);
    setRows([]);
    setReviewGroups([]);
    setSummary(null);
    setNotice(null);
  }

  const visibleRows = sortRows(filterRows(rows, statusFilter, categoryFilter, search));
  const filtersOn = statusFilter !== "all" || categoryFilter !== "all" || search !== "";

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white">
            <LogoIcon className="h-5 w-5" />
          </div>
          <div>
            <p className="font-semibold leading-tight text-slate-900">Driver Statement Categorizer</p>
            <p className="hidden text-xs text-slate-500 sm:block">Tax-time sorting for rideshare and delivery drivers</p>
          </div>
          {session && (
            <button
              type="button"
              onClick={startOver}
              className="ml-auto rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              New statement
            </button>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-4 px-4 py-6">
        {error && (
          <div
            role="alert"
            className="flex items-start justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
          >
            <span>{error}</span>
            <button type="button" onClick={() => setError(null)} className="font-medium hover:underline">
              Dismiss
            </button>
          </div>
        )}

        {notice && (
          <div
            role="status"
            className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900"
          >
            <CheckIcon className="h-4 w-4 text-emerald-600" />
            {notice}
          </div>
        )}

        {/* Step 1: no statement yet */}
        {!session && <UploadZone busy={uploading} onUpload={handleUpload} onError={setError} />}

        {/* Step 2: statement uploaded */}
        {session && (
          <>
            {session.file_summaries.map((file) => (
              <FileSummaryCard key={file.file_name} summary={file} taxYear={session.tax_year} />
            ))}

            <SummaryCards rows={rows} summary={summary} />

            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
              <div className="min-w-0 space-y-4">
                <ReviewQueue groups={reviewGroups} categories={categories} saving={saving} onApply={fixReviewGroup} />

                <section className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h2 className="text-lg font-semibold text-slate-900">Transactions</h2>
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

                  <TxTable
                    rows={visibleRows}
                    categories={categories}
                    saving={saving}
                    onCategoryChange={changeCategory}
                    onBusinessPctChange={changeBusinessPct}
                  />
                </section>
              </div>

              <aside className="lg:sticky lg:top-4 lg:self-start">
                {summary && <Totals summary={summary} exportUrl={exportUrl(session.session_id)} />}
              </aside>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
