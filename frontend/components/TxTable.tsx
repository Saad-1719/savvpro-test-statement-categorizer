"use client";

// The table of every row in the statement.
// Each row shows the description with the backend's reason under it, the amount,
// the category (editable) and a status badge. Clicking the badge opens the details:
// the rule that decided the row and all the evidence the backend found.

import { Fragment, useState } from "react";
import { CategorySelect } from "./CategorySelect";
import { isMixedUse, isMoneyIn, money, STATUS_LABELS } from "@/lib/format";
import type { Category, Row, Status } from "@/lib/types";

const BADGE_COLORS: Record<Status, string> = {
  review: "bg-amber-50 text-amber-800 ring-amber-200",
  auto: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  excluded: "bg-slate-50 text-slate-600 ring-slate-200",
};

const DOT_COLORS: Record<Status, string> = {
  review: "bg-amber-400",
  auto: "bg-emerald-500",
  excluded: "bg-slate-400",
};

const FLAG_TEXT: Record<string, string> = {
  duplicate: "Possible duplicate",
  outside_tax_year: "Outside tax year, not counted",
};

interface Props {
  rows: Row[];
  categories: Category[];
  saving: boolean;
  onCategoryChange: (row: Row, category: string) => void;
  onBusinessPctChange: (row: Row, pct: number) => void;
}

export function TxTable({ rows, categories, saving, onCategoryChange, onBusinessPctChange }: Props) {
  if (rows.length === 0) {
    return (
      <p className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
        No rows match these filters.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="w-full min-w-[46rem] text-left text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-xs font-medium text-slate-500">
          <tr>
            <th className="px-4 py-2.5">Date</th>
            <th className="px-4 py-2.5">Description</th>
            <th className="px-4 py-2.5 text-right">Amount</th>
            <th className="px-4 py-2.5">Category</th>
            <th className="px-4 py-2.5">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <TableRow
              key={row.id}
              row={row}
              categories={categories}
              saving={saving}
              onCategoryChange={onCategoryChange}
              onBusinessPctChange={onBusinessPctChange}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface RowProps {
  row: Row;
  categories: Category[];
  saving: boolean;
  onCategoryChange: (row: Row, category: string) => void;
  onBusinessPctChange: (row: Row, pct: number) => void;
}

function TableRow({ row, categories, saving, onCategoryChange, onBusinessPctChange }: RowProps) {
  const [showDetails, setShowDetails] = useState(false);
  const decision = row.decision;
  const detailsId = `details-${row.id}`;
  const needsReview = decision.status === "review";
  // Flagged rows are not counted, unless the user kept a duplicate by giving it a category.
  const notCounted = row.flags.length > 0 && decision.decided_by !== "user";
  // A duplicate may be a real second purchase, so it stays editable. A row from another
  // tax year must never count, so it is locked.
  const locked = row.flags.includes("outside_tax_year");

  let rowStyle = "hover:bg-slate-50";
  if (notCounted) rowStyle = "bg-slate-50/60 text-slate-400";
  else if (needsReview) rowStyle = "bg-amber-50/70 hover:bg-amber-50";

  let placeholder = "Choose…";
  if (locked) placeholder = "Not counted";
  else if (notCounted) placeholder = "Not counted (pick to keep)";
  else if (decision.suggestion) placeholder = `Suggested: ${decision.suggestion}`;

  let amountColor = "text-slate-900";
  if (notCounted) amountColor = "text-slate-400 line-through";
  else if (isMoneyIn(row.amount)) amountColor = "text-emerald-700";

  return (
    <Fragment>
      <tr className={rowStyle}>
        <td className="whitespace-nowrap px-4 py-3 align-top tabular-nums text-slate-500">{row.date}</td>

        <td className="px-4 py-3 align-top">
          <p className={"font-mono text-xs " + (notCounted ? "" : "text-slate-900")}>{row.raw_description}</p>
          <p className={"mt-0.5 text-xs " + (needsReview ? "text-amber-800" : "text-slate-500")}>{decision.reason}</p>
          {row.flags.map((flag) => (
            <span
              key={flag}
              className="mr-1 mt-1 inline-block rounded bg-slate-200 px-1.5 py-0.5 text-[11px] text-slate-600"
            >
              {FLAG_TEXT[flag] || flag}
            </span>
          ))}
        </td>

        <td className={"whitespace-nowrap px-4 py-3 text-right align-top font-medium tabular-nums " + amountColor}>
          {money(row.amount)}
        </td>

        <td className="w-52 px-4 py-3 align-top">
          <CategorySelect
            label={`Category for ${row.raw_description}`}
            categories={categories}
            value={decision.category}
            placeholder={placeholder}
            onChange={(category) => onCategoryChange(row, category)}
            disabled={saving || locked}
          />

          {/* Phone & Data and other mixed-use rows need a business-use % */}
          {isMixedUse(categories, decision.category) && (
            <label className="mt-1.5 flex items-center gap-1 text-xs text-slate-600">
              Business use
              <input
                // The key changes whenever the saved % changes, which resets the box to the saved value.
                key={String(decision.business_pct)}
                type="number"
                min={0}
                max={100}
                step={1}
                aria-label={`Business-use percent for ${row.raw_description}`}
                defaultValue={decision.business_pct ?? ""}
                placeholder="?"
                disabled={saving}
                onBlur={(e) => {
                  const typed = e.target.value;
                  if (typed !== "" && Number(typed) !== decision.business_pct) onBusinessPctChange(row, Number(typed));
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") e.currentTarget.blur();
                }}
                className={
                  "w-14 rounded-md border px-1.5 py-0.5 text-right " +
                  (decision.business_pct === null ? "border-amber-400 bg-amber-50" : "border-slate-300")
                }
              />
              %
            </label>
          )}

          {decision.refund_of && <p className="mt-1 text-xs text-slate-500">Reduces {decision.refund_of}</p>}
        </td>

        <td className="whitespace-nowrap px-4 py-3 align-top">
          <button
            type="button"
            aria-expanded={showDetails}
            aria-controls={detailsId}
            onClick={() => setShowDetails(!showDetails)}
            className={
              "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset hover:brightness-95 " +
              BADGE_COLORS[decision.status]
            }
          >
            <span className={"h-1.5 w-1.5 rounded-full " + DOT_COLORS[decision.status]} />
            {STATUS_LABELS[decision.status]}
            <span className="sr-only">: show why</span>
          </button>
          {decision.decided_by === "user" && (
            <span
              title="You chose this category"
              className="ml-1 rounded-full bg-indigo-50 px-1.5 py-0.5 text-[11px] font-semibold text-indigo-700"
            >
              you
            </span>
          )}
        </td>
      </tr>

      {showDetails && (
        <tr id={detailsId} className="bg-slate-50">
          <td colSpan={5} className="px-4 pb-3 pt-1">
            <DecisionDetails row={row} />
          </td>
        </tr>
      )}
    </Fragment>
  );
}

// Why the backend decided what it did: the deciding rule plus every piece of evidence it collected.
function DecisionDetails({ row }: { row: Row }) {
  const decision = row.decision;
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-700">
      <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-[auto_1fr]">
        <dt className="text-slate-500">Decision</dt>
        <dd>{decision.reason}</dd>
        <dt className="text-slate-500">Rule</dt>
        <dd className="font-mono">{decision.rule_id ?? "none"}</dd>
        <dt className="text-slate-500">Merchant key</dt>
        <dd className="font-mono">{decision.merchant_key}</dd>
        <dt className="text-slate-500">Decided by</dt>
        <dd>{decision.decided_by === "user" ? "You" : "The app's rules"}</dd>
        {decision.suggestion && (
          <>
            <dt className="text-slate-500">Suggestion</dt>
            <dd>{decision.suggestion}</dd>
          </>
        )}
      </dl>
      {decision.evidence.length > 0 && (
        <>
          <p className="mt-2 font-medium text-slate-600">Evidence found</p>
          <ul className="mt-1 space-y-0.5">
            {decision.evidence.map((item) => (
              <li key={item.rule_id}>
                <span className="font-mono text-slate-500">{item.rule_id}</span> ({item.layer}, {item.strength}):{" "}
                {item.reason}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
