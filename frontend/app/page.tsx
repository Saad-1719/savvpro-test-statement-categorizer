"use client";

// The whole app is this one page:
//   1. Before upload: show the upload screen.
//   2. After upload: show the file summary, the summary cards, the Needs Review queue,
//      the transactions table and the totals.
// The data and the actions that change it live in useStatementSession; this file only lays things out.

import { FileSummaryCard } from "@/components/FileSummaryCard";
import { CheckIcon, LogoIcon } from "@/components/icons";
import { ReviewQueue } from "@/components/ReviewQueue";
import { SummaryCards } from "@/components/SummaryCards";
import { Totals } from "@/components/Totals";
import { TransactionsSection } from "@/components/TransactionsSection";
import { UploadZone } from "@/components/UploadZone";
import { exportUrl } from "@/lib/api";
import { useStatementSession } from "@/lib/useStatementSession";

export default function Home() {
  const app = useStatementSession();
  const session = app.session;

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

          <div className="ml-auto flex items-center gap-3">
            {/* Announced to screen readers; shown while a change is being saved. */}
            <p role="status" aria-live="polite" className="text-sm text-slate-500">
              {app.saving ? "Saving…" : ""}
            </p>
            {session && (
              <button
                type="button"
                onClick={app.startOver}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                New statement
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-4 px-4 py-6">
        {app.error && (
          <div
            role="alert"
            className="flex items-start justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
          >
            <span>{app.error}</span>
            <button type="button" onClick={app.dismissError} className="font-medium hover:underline">
              Dismiss
            </button>
          </div>
        )}

        {app.notice && (
          <div
            role="status"
            className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900"
          >
            <CheckIcon className="h-4 w-4 text-emerald-600" />
            {app.notice}
          </div>
        )}

        {/* Step 1: no statement yet */}
        {!session && (
          <UploadZone busy={app.uploading || app.loadingCategories} onUpload={app.upload} onError={app.showError} />
        )}

        {/* Step 2: statement uploaded */}
        {session && (
          <>
            {session.file_summaries.map((file) => (
              <FileSummaryCard key={file.file_name} summary={file} taxYear={session.tax_year} />
            ))}

            <SummaryCards rows={app.rows} summary={app.summary} />

            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
              <div className="min-w-0 space-y-4">
                <ReviewQueue
                  groups={app.reviewGroups}
                  categories={app.categories}
                  saving={app.saving}
                  onApply={app.fixReviewGroup}
                />
                <TransactionsSection
                  rows={app.rows}
                  categories={app.categories}
                  saving={app.saving}
                  onCategoryChange={app.changeCategory}
                  onBusinessPctChange={app.changeBusinessPct}
                />
              </div>

              <aside className="lg:sticky lg:top-4 lg:self-start">
                {app.summary ? (
                  <Totals summary={app.summary} exportUrl={exportUrl(session.session_id)} />
                ) : (
                  <div className="h-64 animate-pulse rounded-xl border border-slate-200 bg-white" aria-hidden="true" />
                )}
              </aside>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
