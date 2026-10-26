// Small helpers for showing data on screen.
// None of these decide a category. The backend does that.
import type { Category, Row, Status } from "./types";

const dollars = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

// "-18.40" -> "-$18.40". The API sends money as text so no cents get lost; we only format it here.
export function money(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  const number = Number(value);
  if (Number.isNaN(number)) {
    return value;
  }
  return dollars.format(number);
}

// True when the amount is money coming in (a positive number).
export function isMoneyIn(value: string): boolean {
  return Number(value) > 0;
}

// The API sends category kinds in snake_case. These are the labels we show.
const KIND_LABELS: Record<string, string> = {
  income: "Income",
  expense: "Expense",
  contra: "Refund",
  personal: "Personal (not deductible)",
  excluded: "Excluded",
};

export function kindLabel(kind: string): string {
  return KIND_LABELS[kind] || kind;
}

// Mixed-use categories (like Phone & Data) need a business-use % before they count.
// The API tells us which categories are mixed-use, so we don't hardcode names.
export function isMixedUse(categories: Category[], categoryName: string | null): boolean {
  const category = categories.find((c) => c.name === categoryName);
  return category !== undefined && category.mixed_use;
}

export const STATUS_LABELS: Record<Status, string> = {
  review: "Needs Review",
  auto: "Auto",
  excluded: "Excluded",
};

// Needs Review rows go first, then oldest date first, then the order they were in the statement.
export function sortRows(rows: Row[]): Row[] {
  const statusOrder: Record<Status, number> = { review: 0, auto: 1, excluded: 2 };

  return [...rows].sort((a, b) => {
    const statusDifference = statusOrder[a.decision.status] - statusOrder[b.decision.status];
    if (statusDifference !== 0) {
      return statusDifference;
    }
    if (a.date !== b.date) {
      return a.date < b.date ? -1 : 1;
    }
    return a.row_number - b.row_number;
  });
}

// Keeps only the rows that match the filters. "all" means that filter is off.
export function filterRows(rows: Row[], status: string, category: string, search: string): Row[] {
  const searchText = search.trim().toUpperCase();

  return rows.filter((row) => {
    if (status !== "all" && row.decision.status !== status) {
      return false;
    }
    if (category !== "all" && row.decision.category !== category) {
      return false;
    }
    if (searchText !== "" && !row.raw_description.toUpperCase().includes(searchText)) {
      return false;
    }
    return true;
  });
}

// Text shown when hovering a status badge: why the row got this status.
export function statusTooltip(row: Row): string {
  const decision = row.decision;
  const lines = [decision.reason];
  if (decision.rule_id) lines.push(`Rule: ${decision.rule_id}`);
  if (decision.suggestion) lines.push(`Suggestion: ${decision.suggestion}`);
  if (decision.refund_of) lines.push(`Refund of: ${decision.refund_of}`);
  return lines.join("\n");
}
