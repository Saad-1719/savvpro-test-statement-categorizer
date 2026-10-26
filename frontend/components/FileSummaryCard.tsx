"use client";

// One line about the uploaded file: name, layout, dates and anything left out.
// "Details" opens the full numbers and the list of skipped rows.

import { useState } from "react";
import { FileIcon } from "./icons";
import { money } from "@/lib/format";
import type { FileSummary } from "@/lib/types";

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

export function FileSummaryCard({ summary, taxYear }: { summary: FileSummary; taxYear: number }) {
  const [open, setOpen] = useState(false);
  const skipped = summary.rows_skipped.length;

  // Short notes about rows that were read but are not counted, or lines that were not rows at all.
  const notes: string[] = [];
  if (summary.duplicates > 0) notes.push(plural(summary.duplicates, "duplicate"));
  if (summary.outside_tax_year > 0) notes.push(`${summary.outside_tax_year} outside ${taxYear}`);
  if (skipped > 0) notes.push(plural(skipped, "unreadable row"));

  const stats: [string, string][] = [
    ["Rows read", String(summary.rows_read)],
    ["Money in", money(summary.money_in)],
    ["Money out", money(summary.money_out)],
    ["Header lines skipped", String(summary.junk_rows_before_header)],
    ["Footer lines skipped", String(summary.footer_rows)],
    ["Duplicates", String(summary.duplicates)],
    [`Outside ${taxYear}`, String(summary.outside_tax_year)],
    ["Unreadable rows", String(skipped)],
  ];

  return (
    <section className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <FileIcon className="h-5 w-5 text-slate-400" />
        <p className="font-medium text-slate-900">{summary.file_name}</p>
        <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-600">{summary.layout}</span>
        <p className="text-sm text-slate-500">
          {summary.rows_read} rows
          {summary.date_from && ` · ${summary.date_from} to ${summary.date_to}`} · tax year {taxYear}
        </p>
        {notes.length > 0 && (
          <p className="text-sm text-slate-500">
            · <span className="text-slate-700">{notes.join(", ")}</span> not counted
          </p>
        )}
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="ml-auto text-sm font-medium text-indigo-600 hover:underline"
        >
          {open ? "Hide details" : "Details"}
        </button>
      </div>

      {open && (
        <div className="mt-3 border-t border-slate-100 pt-3">
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {stats.map(([label, value]) => (
              <div key={label}>
                <dt className="text-xs text-slate-500">{label}</dt>
                <dd className="font-medium tabular-nums text-slate-900">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-xs text-slate-500">
            Duplicates and rows outside the tax year stay in the table, marked, but are left out of the totals.
          </p>
          {skipped > 0 && (
            <ul className="mt-2 space-y-1 text-sm text-slate-700">
              {summary.rows_skipped.map((s) => (
                <li key={s.row_number}>
                  <span className="font-mono text-slate-500">Line {s.row_number}:</span> {s.reason}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
