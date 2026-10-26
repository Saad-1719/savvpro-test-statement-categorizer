// Renders the whole page against a fake backend (fetch is replaced) and walks through
// upload -> fix a Needs Review group -> totals become Final.
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Home from "../app/page";
import { categories, makeGroup, makeRow, makeSummary } from "./fixtures";
import type { Row } from "../lib/types";

// The fake backend's state for one session.
let rows: Row[];
let calls: { method: string; path: string; body: unknown }[];

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function fakeBackend(overrides: Record<string, () => Response> = {}) {
  return vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = init.method ?? "GET";
    const path = new URL(url).pathname;
    const body = typeof init.body === "string" ? JSON.parse(init.body) : null;
    calls.push({ method, path, body });

    const key = `${method} ${path}`;
    if (overrides[key]) return overrides[key]();

    const reviewRows = rows.filter((r) => r.decision.status === "review");
    if (key === "GET /api/categories") return json(categories);
    if (key === "POST /api/sessions") {
      return json({ session_id: "s1", tax_year: 2025, file_summaries: [fileSummary], transactions: rows });
    }
    if (key === "GET /api/sessions/s1/transactions") return json(rows);
    if (key === "GET /api/sessions/s1/review") {
      return json(reviewRows.length ? [makeGroup("JOES CAFE", reviewRows.map((r) => r.id))] : []);
    }
    if (key === "GET /api/sessions/s1/summary") {
      return json(makeSummary({ is_final: reviewRows.length === 0, unreviewed_count: reviewRows.length }));
    }
    if (key === "PATCH /api/sessions/s1/transactions") {
      const { transaction_ids, category } = body as { transaction_ids: string[]; category: string };
      rows = rows.map((r) =>
        transaction_ids.includes(r.id)
          ? { ...r, decision: { ...r.decision, status: "auto", category, decided_by: "user", rule_id: "user.manual" } }
          : r,
      );
      return json(rows.filter((r) => transaction_ids.includes(r.id)));
    }
    return json({ error: { code: "not_found", message: `No fake for ${key}`, details: {} } }, 404);
  });
}

const fileSummary = {
  file_name: "statement.csv",
  layout: "first_federal_checking",
  rows_read: 3,
  rows_skipped: [],
  junk_rows_before_header: 4,
  footer_rows: 2,
  duplicates: 0,
  outside_tax_year: 0,
  date_from: "2025-01-03",
  date_to: "2025-02-14",
  money_in: "412.30",
  money_out: "-21.00",
};

async function uploadStatement() {
  render(<Home />);
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  await waitFor(() => expect(screen.getByRole("button", { name: "Choose file" })).toBeEnabled());
  await userEvent.upload(input, new File(["csv"], "statement.csv", { type: "text/csv" }));
  await screen.findByText("statement.csv");
}

beforeEach(() => {
  calls = [];
  rows = [
    makeRow("t1", "UBER TECHNOLOGIES PAYOUT", "412.30", { category: "Platform Income" }),
    makeRow("t2", "JOES CAFE 9921", "-8.75", { status: "review", category: null, reason: "Unknown merchant" }),
    makeRow("t3", "JOES CAFE 9921", "-12.25", { status: "review", category: null, reason: "Unknown merchant" }),
  ];
});

describe("the whole page", () => {
  it("uploads, fixes a review group with one bulk request, and finishes with Final totals", async () => {
    vi.stubGlobal("fetch", fakeBackend());
    await uploadStatement();

    expect(screen.getByText(/needs review: 2 rows from 1 merchant/i)).toBeInTheDocument();
    expect(screen.getAllByText("Draft").length).toBeGreaterThan(0);

    await userEvent.selectOptions(screen.getByLabelText("Category for JOES CAFE"), "Personal");
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));

    await screen.findByText(/nothing left to review/i);
    const bulk = calls.filter((c) => c.method === "PATCH");
    expect(bulk).toHaveLength(1);
    expect(bulk[0]).toEqual({
      method: "PATCH",
      path: "/api/sessions/s1/transactions",
      body: { transaction_ids: ["t2", "t3"], category: "Personal" },
    });

    const totals = screen.getByRole("heading", { name: "Totals" }).closest("section")!;
    expect(within(totals).getByText("Final")).toBeInTheDocument();
    expect(screen.getAllByText("you")).toHaveLength(2);
    expect(within(totals).getByRole("link", { name: /export csv/i })).toHaveAttribute(
      "href",
      "http://localhost:8000/api/sessions/s1/export.csv",
    );
  });

  it("shows the backend's message when an upload is refused", async () => {
    vi.stubGlobal(
      "fetch",
      fakeBackend({
        "POST /api/sessions": () =>
          json({ error: { code: "unrecognized_layout", message: "Unrecognized statement layout.", details: {} } }, 422),
      }),
    );
    render(<Home />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Choose file" })).toBeEnabled());
    await userEvent.upload(
      document.querySelector('input[type="file"]') as HTMLInputElement,
      new File(["x"], "weird.csv", { type: "text/csv" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("Unrecognized statement layout.");
    expect(screen.getByText("Drop your bank statement here")).toBeInTheDocument();
  });

  it("keeps the group in review and explains why when the bulk save fails", async () => {
    vi.stubGlobal(
      "fetch",
      fakeBackend({
        "PATCH /api/sessions/s1/transactions": () =>
          json({ error: { code: "transaction_not_found", message: "Transaction not found.", details: {} } }, 404),
      }),
    );
    await uploadStatement();
    await userEvent.selectOptions(screen.getByLabelText("Category for JOES CAFE"), "Personal");
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Transaction not found.");
    expect(screen.getByText(/needs review: 2 rows/i)).toBeInTheDocument();
  });

  it("tells the user to upload again when the session is gone", async () => {
    vi.stubGlobal(
      "fetch",
      fakeBackend({
        "PATCH /api/sessions/s1/transactions": () =>
          json({ error: { code: "session_not_found", message: "Session not found.", details: {} } }, 404),
      }),
    );
    await uploadStatement();
    await userEvent.selectOptions(screen.getByLabelText("Category for JOES CAFE"), "Personal");
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/please upload it again/i);
  });

  it("filters the table by status", async () => {
    vi.stubGlobal("fetch", fakeBackend());
    await uploadStatement();
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(4); // header + 3 rows

    const filters = screen.getByRole("group", { name: "Filter by status" });
    await userEvent.click(within(filters).getByRole("button", { name: /auto/i }));
    expect(within(table).getAllByRole("row")).toHaveLength(2);
    expect(within(table).getByText("UBER TECHNOLOGIES PAYOUT")).toBeInTheDocument();
  });
});
