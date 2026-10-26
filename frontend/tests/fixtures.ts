// Small builders for fake API data used across the tests.
import type { Category, Decision, ReviewGroup, Row, Summary } from "../lib/types";

export const categories: Category[] = [
  { name: "Platform Income", kind: "income", tax_line: "1", tax_line_label: "Gross receipts", mixed_use: false },
  { name: "Fuel", kind: "expense", tax_line: "9", tax_line_label: "Car and truck expenses", mixed_use: false },
  { name: "Phone & Data", kind: "expense", tax_line: "25", tax_line_label: "Utilities", mixed_use: true },
  { name: "Personal", kind: "personal", tax_line: null, tax_line_label: null, mixed_use: false },
  { name: "Transfer", kind: "excluded", tax_line: null, tax_line_label: null, mixed_use: false },
];

export function makeRow(id: string, description: string, amount: string, decision: Partial<Decision> = {}, extra: Partial<Row> = {}): Row {
  return {
    id,
    source_file: "statement.csv",
    row_number: Number(id.replace(/\D/g, "")) || 1,
    date: "2025-01-10",
    raw_description: description,
    amount,
    account: "checking",
    flags: [],
    decision: {
      merchant_key: description,
      status: "auto",
      category: "Fuel",
      suggestion: null,
      reason: "Known merchant",
      rule_id: "merchant.test",
      evidence: [],
      refund_of: null,
      business_pct: null,
      decided_by: "brain",
      ...decision,
    },
    ...extra,
  };
}

export function makeGroup(merchantKey: string, ids: string[], extra: Partial<ReviewGroup> = {}): ReviewGroup {
  return {
    merchant_key: merchantKey,
    count: ids.length,
    total: "-21.00",
    reason: "Unknown merchant",
    suggestion: null,
    transaction_ids: ids,
    ...extra,
  };
}

export function makeSummary(extra: Partial<Summary> = {}): Summary {
  return {
    tax_year: 2025,
    totals: [
      { category: "Platform Income", kind: "income", amount: "412.30", deductible_amount: null, tax_line: "1" },
      { category: "Fuel", kind: "expense", amount: "-48.15", deductible_amount: "48.15", tax_line: "9" },
      { category: "Phone & Data", kind: "expense", amount: "-85.00", deductible_amount: "51.00", tax_line: "25" },
    ],
    income_total: "412.30",
    deductible_total: "99.15",
    unreviewed_amount: "21.00",
    unreviewed_count: 2,
    phone_missing_pct_count: 0,
    is_final: false,
    tax_form_name: "Schedule C (Form 1040)",
    tax_form_lines: [
      { line: "1", label: "Gross receipts", amount: "412.30" },
      { line: "9", label: "Car and truck expenses", amount: "48.15" },
    ],
    tax_form_note: "Informational only.",
    ...extra,
  };
}
