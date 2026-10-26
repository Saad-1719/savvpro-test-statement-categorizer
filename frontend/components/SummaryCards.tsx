"use client";

// The four cards at the top of the results: income, deductible expenses,
// what still needs review, and whether the totals are final.

import { AlertIcon, CheckIcon } from "./icons";
import { money } from "@/lib/format";
import type { Row, Summary } from "@/lib/types";

interface Props {
  rows: Row[];
  summary: Summary | null;
}

export function SummaryCards({ rows, summary }: Props) {
  const reviewCount = rows.filter((row) => row.decision.status === "review").length;
  const decidedCount = rows.length - reviewCount;
  const percentDone = rows.length === 0 ? 100 : Math.round((decidedCount / rows.length) * 100);
  const isFinal = summary !== null && summary.is_final;

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Card label="Business income" value={summary ? money(summary.income_total) : "—"} note="Platform payouts and tips" />

      <Card
        label="Deductible expenses"
        value={summary ? money(summary.deductible_total) : "—"}
        note="Business share only"
      />

      <Card
        label="Needs review"
        value={`${reviewCount} ${reviewCount === 1 ? "row" : "rows"}`}
        note={summary ? `${money(summary.unreviewed_amount)} not counted yet` : ""}
        highlight={reviewCount > 0}
      />

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Totals</p>
        <p className={"mt-1 flex items-center gap-1.5 text-xl font-semibold " + (isFinal ? "text-emerald-700" : "text-amber-700")}>
          {isFinal ? <CheckIcon className="h-5 w-5" /> : <AlertIcon className="h-5 w-5" />}
          {isFinal ? "Final" : "Draft"}
        </p>
        <div className="mt-2 h-1.5 rounded-full bg-slate-100">
          <div
            className={"h-1.5 rounded-full " + (isFinal ? "bg-emerald-500" : "bg-amber-400")}
            style={{ width: `${percentDone}%` }}
          />
        </div>
        <p className="mt-1 text-xs text-slate-500">
          {decidedCount} of {rows.length} rows decided
          {summary && summary.phone_missing_pct_count > 0 && ` · ${summary.phone_missing_pct_count} need a business %`}
        </p>
      </div>
    </div>
  );
}

interface CardProps {
  label: string;
  value: string;
  note: string;
  highlight?: boolean;
}

function Card({ label, value, note, highlight = false }: CardProps) {
  const style = highlight ? "border-amber-300 bg-amber-50" : "border-slate-200 bg-white";
  return (
    <div className={"rounded-xl border p-4 shadow-sm " + style}>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums text-slate-900">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{note}</p>
    </div>
  );
}
