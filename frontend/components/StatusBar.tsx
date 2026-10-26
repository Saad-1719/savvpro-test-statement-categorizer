"use client";

// Tabs above the table: All, Needs Review, Auto, Excluded, each with its row count.
// Clicking a tab filters the table to that status.

import { STATUS_LABELS } from "@/lib/format";
import type { Row, Status } from "@/lib/types";

const DOT_COLORS: Record<Status, string> = {
  review: "bg-amber-400",
  auto: "bg-emerald-500",
  excluded: "bg-slate-400",
};

const STATUSES: Status[] = ["review", "auto", "excluded"];

interface Props {
  rows: Row[];
  active: string; // the status currently filtered on, or "all"
  onSelect: (status: string) => void;
}

export function StatusBar({ rows, active, onSelect }: Props) {
  function countRows(status: Status): number {
    return rows.filter((row) => row.decision.status === status).length;
  }

  return (
    <div role="tablist" aria-label="Filter by status" className="inline-flex flex-wrap rounded-lg bg-slate-100 p-1">
      <Tab label="All" count={rows.length} isActive={active === "all"} onClick={() => onSelect("all")} />
      {STATUSES.map((status) => (
        <Tab
          key={status}
          label={STATUS_LABELS[status]}
          count={countRows(status)}
          dotColor={DOT_COLORS[status]}
          isActive={active === status}
          onClick={() => onSelect(status)}
        />
      ))}
    </div>
  );
}

interface TabProps {
  label: string;
  count: number;
  isActive: boolean;
  dotColor?: string;
  onClick: () => void;
}

function Tab({ label, count, isActive, dotColor, onClick }: TabProps) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={isActive}
      onClick={onClick}
      className={
        "flex items-center gap-1.5 rounded-md px-3 py-1 text-sm font-medium " +
        (isActive ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900")
      }
    >
      {dotColor && <span className={"h-2 w-2 rounded-full " + dotColor} />}
      {label}
      <span className="tabular-nums text-slate-400">{count}</span>
    </button>
  );
}
