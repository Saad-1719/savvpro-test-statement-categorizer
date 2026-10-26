"use client";

// The Needs Review list. Rows are grouped by merchant, so one choice fixes every row in the group.

import { useState } from "react";
import { CategorySelect } from "./CategorySelect";
import { AlertIcon, CheckIcon } from "./icons";
import { isMixedUse, money } from "@/lib/format";
import type { Category, ReviewGroup } from "@/lib/types";
import type { GroupFix } from "@/lib/useStatementSession";

interface Props {
  groups: ReviewGroup[];
  categories: Category[];
  saving: boolean;
  onApply: (group: ReviewGroup, fix: GroupFix) => void;
}

export function ReviewQueue({ groups, categories, saving, onApply }: Props) {
  if (groups.length === 0) {
    return (
      <section className="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
        <CheckIcon className="h-5 w-5 text-emerald-600" />
        Nothing left to review. Every row has a category.
      </section>
    );
  }

  const rowCount = groups.reduce((sum, group) => sum + group.count, 0);

  return (
    <section className="overflow-hidden rounded-xl border border-amber-300 bg-white shadow-sm">
      <div className="flex items-start gap-3 border-b border-amber-200 bg-amber-50 px-4 py-3">
        <AlertIcon className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
        <div>
          <h2 className="font-semibold text-amber-950">
            Needs review: {rowCount} {rowCount === 1 ? "row" : "rows"} from {groups.length}{" "}
            {groups.length === 1 ? "merchant" : "merchants"}
          </h2>
          <p className="text-sm text-amber-900">
            The app was not sure about these, so it didn&apos;t guess. Pick a category once and it applies to every row
            from that merchant. Tick <b>Always</b> to remember it for future statements.
          </p>
        </div>
      </div>
      <ul className="divide-y divide-slate-100">
        {groups.map((group) => (
          <ReviewGroupItem
            key={group.merchant_key}
            group={group}
            categories={categories}
            saving={saving}
            onApply={onApply}
          />
        ))}
      </ul>
    </section>
  );
}

interface ItemProps {
  group: ReviewGroup;
  categories: Category[];
  saving: boolean;
  onApply: (group: ReviewGroup, fix: GroupFix) => void;
}

// One merchant group. It has its own state: the chosen category, the "Always" box and the business %.
function ReviewGroupItem({ group, categories, saving, onApply }: ItemProps) {
  const [category, setCategory] = useState<string | null>(group.suggestion);
  const [always, setAlways] = useState(false);
  const [pct, setPct] = useState("");

  const needsPct = isMixedUse(categories, category);
  const pctIsValid = pct !== "" && Number(pct) >= 0 && Number(pct) <= 100;
  const canApply = category !== null && (!needsPct || pctIsValid) && !saving;

  function apply() {
    if (category === null) return;
    onApply(group, {
      category: category,
      always: always,
      businessPct: needsPct ? Math.round(Number(pct)) : undefined,
    });
  }

  return (
    <li className="flex flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3">
      <div className="min-w-[14rem] flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <p className="font-mono text-sm font-semibold text-slate-900">{group.merchant_key}</p>
          <p className="text-sm tabular-nums text-slate-500">
            {group.count} {group.count === 1 ? "row" : "rows"} · {money(group.total)}
          </p>
        </div>
        <p className="mt-0.5 text-sm text-slate-600">{group.reason}</p>
        {group.suggestion && (
          <p className="mt-0.5 text-xs text-slate-500">
            Suggested: <span className="font-medium text-slate-700">{group.suggestion}</span>. Not applied until you
            click Apply.
          </p>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="w-48">
          <CategorySelect
            label={`Category for ${group.merchant_key}`}
            categories={categories}
            value={category}
            onChange={setCategory}
            disabled={saving}
          />
        </div>

        {needsPct && (
          <label className="flex items-center gap-1 text-sm text-slate-700">
            <input
              type="number"
              min={0}
              max={100}
              value={pct}
              onChange={(e) => setPct(e.target.value)}
              placeholder="%"
              className="w-16 rounded-md border border-amber-400 px-2 py-1 text-right"
            />
            % business
          </label>
        )}

        <label className="flex items-center gap-1.5 text-sm text-slate-700" title="Remember this for future statements">
          <input
            type="checkbox"
            checked={always}
            onChange={(e) => setAlways(e.target.checked)}
            disabled={saving}
            className="h-4 w-4 rounded border-slate-300 accent-indigo-600"
          />
          Always
        </label>

        <button
          type="button"
          disabled={!canApply}
          onClick={apply}
          className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:bg-slate-200 disabled:text-slate-500"
        >
          {saving ? "Saving…" : "Apply"}
        </button>
      </div>
    </li>
  );
}
