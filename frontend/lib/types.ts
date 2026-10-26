// Shapes returned by the backend API. Money values are decimal strings like "-18.40".

export type Status = "auto" | "review" | "excluded";
export type Strength = "strong" | "medium" | "weak";
export type RowFlag = "duplicate" | "outside_tax_year";

export interface Evidence {
  layer: string;
  rule_id: string;
  category: string | null;
  strength: Strength;
  reason: string;
}

export interface Decision {
  merchant_key: string;
  status: Status;
  category: string | null;
  suggestion: string | null;
  reason: string;
  rule_id: string | null;
  evidence: Evidence[];
  refund_of: string | null;
  business_pct: number | null;
  decided_by: "brain" | "user";
}

export interface Row {
  id: string;
  source_file: string;
  row_number: number;
  date: string;
  raw_description: string;
  amount: string;
  account: string;
  flags: RowFlag[];
  decision: Decision;
}

export interface SkippedRow {
  row_number: number;
  reason: string;
}

export interface FileSummary {
  file_name: string;
  layout: string;
  rows_read: number;
  rows_skipped: SkippedRow[];
  junk_rows_before_header: number;
  footer_rows: number;
  duplicates: number;
  outside_tax_year: number;
  date_from: string | null;
  date_to: string | null;
  money_in: string;
  money_out: string;
}

export interface Session {
  session_id: string;
  tax_year: number;
  file_summaries: FileSummary[];
  transactions: Row[];
}

export interface ReviewGroup {
  merchant_key: string;
  count: number;
  total: string;
  reason: string;
  suggestion: string | null;
  transaction_ids: string[];
}

export type CategoryKind = "income" | "expense" | "contra" | "personal" | "excluded";

export interface CategoryTotal {
  category: string;
  kind: CategoryKind;
  /** Signed net; refunds are already netted into the category they reduce. */
  amount: string;
  /** Expense kinds only; after business-use % for mixed-use categories. */
  deductible_amount: string | null;
  /** Line on the tax form (see Summary.tax_form_name); null when not on the form. */
  tax_line: string | null;
}

/** Category totals added up by tax-form line, e.g. line 9 = all car costs. */
export interface TaxFormLine {
  line: string;
  label: string;
  amount: string;
}

export interface Summary {
  tax_year: number;
  totals: CategoryTotal[];
  income_total: string;
  deductible_total: string;
  unreviewed_amount: string;
  unreviewed_count: number;
  phone_missing_pct_count: number;
  is_final: boolean;
  tax_form_name: string;
  tax_form_lines: TaxFormLine[];
  tax_form_note: string;
}

export interface Category {
  name: string;
  kind: CategoryKind;
  tax_line: string | null;
  tax_line_label: string | null;
  /** Mixed personal/business use: rows need a business_pct before they count. */
  mixed_use: boolean;
}

export interface UserRule {
  rule: { id: string; merchant_key: string; category: string };
  updated_count: number;
}
