import { describe, expect, it } from "vitest";
import { filterRows, isMixedUse, isMoneyIn, kindLabel, money, sortRows, statusTooltip } from "../lib/format";
import type { Row, Status } from "../lib/types";

function row(id: string, status: Status, date: string, extra: Partial<Row["decision"]> = {}): Row {
  return {
    id,
    source_file: "s.csv",
    row_number: Number(id),
    date,
    raw_description: `MERCHANT ${id}`,
    amount: "-10.00",
    account: "checking",
    flags: [],
    decision: {
      merchant_key: `MERCHANT ${id}`,
      status,
      category: status === "review" ? null : "Fuel",
      suggestion: null,
      reason: "reason",
      rule_id: null,
      evidence: [],
      refund_of: null,
      business_pct: null,
      decided_by: "brain",
      ...extra,
    },
  };
}

describe("money", () => {
  it("formats decimal strings as USD", () => {
    expect(money("-18.40")).toBe("-$18.40");
    expect(money("1387.9")).toBe("$1,387.90");
  });
  it("shows a dash for missing values and passes through junk", () => {
    expect(money(null)).toBe("—");
    expect(money("abc")).toBe("abc");
  });
});

describe("isMoneyIn", () => {
  it("is true only for positive amounts", () => {
    expect(isMoneyIn("20.00")).toBe(true);
    expect(isMoneyIn("-20.00")).toBe(false);
    expect(isMoneyIn("0.00")).toBe(false);
  });
});

describe("sortRows", () => {
  it("pins Needs Review rows first, then sorts by date", () => {
    const rows = [row("1", "auto", "2025-01-01"), row("2", "review", "2025-03-01"), row("3", "excluded", "2025-01-02"), row("4", "review", "2025-02-01")];
    expect(sortRows(rows).map((r) => r.id)).toEqual(["4", "2", "1", "3"]);
  });
});

describe("filterRows", () => {
  const rows = [row("1", "auto", "2025-01-01"), row("2", "review", "2025-01-02")];
  it("filters by status and search text", () => {
    expect(filterRows(rows, "review", "all", "").map((r) => r.id)).toEqual(["2"]);
    expect(filterRows(rows, "all", "all", "merchant 1").map((r) => r.id)).toEqual(["1"]);
  });
  it("filters by category", () => {
    expect(filterRows(rows, "all", "Fuel", "").map((r) => r.id)).toEqual(["1"]);
  });
});

describe("statusTooltip", () => {
  it("includes reason, rule id and suggestion", () => {
    const r = row("1", "review", "2025-01-01", { reason: "Amount above fuel limit", rule_id: "merchant.chevron", suggestion: "Fuel" });
    expect(statusTooltip(r)).toBe("Amount above fuel limit\nRule: merchant.chevron\nSuggestion: Fuel");
  });
});

describe("isMixedUse", () => {
  const categories = [
    { name: "Phone & Data", kind: "expense" as const, tax_line: "25", tax_line_label: "Utilities", mixed_use: true },
    { name: "Fuel", kind: "expense" as const, tax_line: "9", tax_line_label: "Car and truck", mixed_use: false },
  ];
  it("uses the API's mixed_use flag, not the category name", () => {
    expect(isMixedUse(categories, "Phone & Data")).toBe(true);
    expect(isMixedUse(categories, "Fuel")).toBe(false);
    expect(isMixedUse(categories, null)).toBe(false);
    expect(isMixedUse([], "Phone & Data")).toBe(false);
  });
});

describe("kindLabel", () => {
  it("maps snake_case kinds to readable labels", () => {
    expect(kindLabel("contra")).toBe("Refund");
    expect(kindLabel("personal")).toBe("Personal (not deductible)");
    expect(kindLabel("something_new")).toBe("something_new");
  });
});
