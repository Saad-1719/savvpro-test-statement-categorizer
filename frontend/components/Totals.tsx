"use client";

// Totals per category (or per tax-form line), the Draft/Final badge and the export button.

import { useState } from "react";
import { DownloadIcon } from "./icons";
import { kindLabel, money } from "@/lib/format";
import type { CategoryTotal, Summary } from "@/lib/types";

// True when only part of a category counts, e.g. Phone & Data at 60% business use.
function isPartlyDeductible(total: CategoryTotal): boolean {
  if (total.deductible_amount === null) return false;
  return Math.abs(Number(total.deductible_amount)) !== Math.abs(Number(total.amount));
}

export function Totals({ summary, exportUrl }: { summary: Summary; exportUrl: string }) {
  const [view, setView] = useState<"categories" | "tax_form">("categories");
  const kinds = Array.from(new Set(summary.totals.map((t) => t.kind)));
  const showTaxForm = summary.tax_form_lines.length > 0;

  return (
    <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <h2 className="font-semibold text-slate-900">Totals</h2>
        {summary.is_final ? (
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">Final</span>
        ) : (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-900">Draft</span>
        )}
      </div>

      <div className="space-y-4 p-4">
        {!summary.is_final && (
          <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">
            Draft until every row is reviewed
            {summary.phone_missing_pct_count > 0 && " and every phone bill has a business-use %"}.
          </p>
        )}

        {showTaxForm && (
          <div role="tablist" className="grid grid-cols-2 rounded-lg bg-slate-100 p-1 text-sm">
            <ViewTab label="By category" isActive={view === "categories"} onClick={() => setView("categories")} />
            <ViewTab label="By tax-form line" isActive={view === "tax_form"} onClick={() => setView("tax_form")} />
          </div>
        )}

        {view === "categories" || !showTaxForm ? (
          kinds.map((kind) => {
            const totalsOfKind = summary.totals.filter((t) => t.kind === kind);
            // In each section the biggest amount is a full-width bar; the others are drawn relative to it.
            const biggest = Math.max(1, ...totalsOfKind.map((t) => Math.abs(Number(t.amount))));
            return (
              <div key={kind}>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{kindLabel(kind)}</h3>
                <ul className="mt-2 space-y-2">
                  {totalsOfKind.map((t) => (
                    <TotalRow key={t.category} total={t} biggest={biggest} />
                  ))}
                </ul>
              </div>
            );
          })
        ) : (
          <div>
            <p className="text-xs font-semibold text-slate-600">{summary.tax_form_name}</p>
            <ul className="mt-2 divide-y divide-slate-100">
              {summary.tax_form_lines.map((line) => (
                <li key={line.line} className="flex items-baseline gap-3 py-1.5 text-sm">
                  <span className="w-14 shrink-0 font-mono text-xs text-slate-500">Line {line.line}</span>
                  <span className="flex-1 text-slate-800">{line.label}</span>
                  <span className="tabular-nums font-medium text-slate-900">{money(line.amount)}</span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-slate-500">
              {summary.tax_form_note || "Informational only. Review with your accountant before filing."}
            </p>
          </div>
        )}

        <a
          href={exportUrl}
          download
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700"
        >
          <DownloadIcon className="h-4 w-4" />
          Export CSV for your accountant
        </a>
      </div>
    </section>
  );
}

function TotalRow({ total, biggest }: { total: CategoryTotal; biggest: number }) {
  const width = Math.round((Math.abs(Number(total.amount)) / biggest) * 100);
  const barColor = total.kind === "income" ? "bg-emerald-400" : total.kind === "expense" ? "bg-indigo-400" : "bg-slate-300";

  return (
    <li>
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="text-slate-800">{total.category}</span>
        <span className="tabular-nums font-medium text-slate-900">{money(total.amount)}</span>
      </div>
      <div className="mt-1 h-1 rounded-full bg-slate-100">
        <div className={"h-1 rounded-full " + barColor} style={{ width: `${width}%` }} />
      </div>
      {isPartlyDeductible(total) && (
        <p className="mt-0.5 text-xs text-slate-500">Deductible: {money(total.deductible_amount)}</p>
      )}
    </li>
  );
}

function ViewTab({ label, isActive, onClick }: { label: string; isActive: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={isActive}
      onClick={onClick}
      className={"rounded-md px-2 py-1 font-medium " + (isActive ? "bg-white text-slate-900 shadow-sm" : "text-slate-600")}
    >
      {label}
    </button>
  );
}
