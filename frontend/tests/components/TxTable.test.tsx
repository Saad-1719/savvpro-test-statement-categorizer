import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TxTable } from "../../components/TxTable";
import { categories, makeRow } from "../fixtures";

function renderTable(rows = [makeRow("1", "SHELL OIL 57442", "-48.15")], handlers = {}) {
  const props = { onCategoryChange: vi.fn(), onBusinessPctChange: vi.fn(), ...handlers };
  render(<TxTable rows={rows} categories={categories} saving={false} {...props} />);
  return props;
}

describe("TxTable", () => {
  it("shows the description, the backend's reason and the amount", () => {
    renderTable();
    expect(screen.getByText("SHELL OIL 57442")).toBeInTheDocument();
    expect(screen.getByText("Known merchant")).toBeInTheDocument();
    expect(screen.getByText("-$48.15")).toBeInTheDocument();
  });

  it("sends a new category when the user picks one", async () => {
    const { onCategoryChange } = renderTable();
    await userEvent.selectOptions(screen.getByLabelText("Category for SHELL OIL 57442"), "Personal");
    expect(onCategoryChange).toHaveBeenCalledWith(expect.objectContaining({ id: "1" }), "Personal");
  });

  it("marks rows the user decided with a 'you' badge", () => {
    renderTable([makeRow("1", "JOES CAFE", "-8.75", { decided_by: "user", category: "Personal" })]);
    expect(screen.getByText("you")).toBeInTheDocument();
  });

  it("opens the decision details with the rule and evidence from the status badge (keyboard accessible)", async () => {
    renderTable([
      makeRow("1", "SAFEWAY FUEL", "-56.40", {
        status: "review",
        category: null,
        reason: "Conflicting rules",
        rule_id: null,
        evidence: [
          { layer: "merchant", rule_id: "merchant.safeway", category: "Personal", strength: "strong", reason: "SAFEWAY is Personal" },
          { layer: "keyword", rule_id: "keyword.fuel", category: "Fuel", strength: "medium", reason: "FUEL suggests Fuel" },
        ],
      }),
    ]);
    const badge = screen.getByRole("button", { name: /needs review/i });
    expect(badge).toHaveAttribute("aria-expanded", "false");

    badge.focus();
    await userEvent.keyboard("{Enter}");

    expect(badge).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("merchant.safeway")).toBeInTheDocument();
    expect(screen.getByText(/FUEL suggests Fuel/)).toBeInTheDocument();
  });

  it("locks rows outside the tax year but lets the user keep a possible duplicate", () => {
    renderTable([
      makeRow("1", "OLD ROW", "-42.10", { status: "excluded", category: null }, { flags: ["outside_tax_year"] }),
      makeRow("2", "JOES CAFE", "-8.75", { status: "excluded", category: null }, { flags: ["duplicate"] }),
    ]);
    expect(screen.getByLabelText("Category for OLD ROW")).toBeDisabled();
    expect(screen.getByLabelText("Category for JOES CAFE")).toBeEnabled();
    expect(screen.getByText("Possible duplicate")).toBeInTheDocument();
  });

  it("saves the business-use % on blur only when it changed", async () => {
    const row = makeRow("1", "VERIZON WRLS", "-85.00", { category: "Phone & Data", business_pct: null });
    const { onBusinessPctChange } = renderTable([row]);
    const input = screen.getByLabelText("Business-use percent for VERIZON WRLS");

    await userEvent.click(input);
    await userEvent.tab();
    expect(onBusinessPctChange).not.toHaveBeenCalled();

    await userEvent.type(input, "60{Enter}");
    expect(onBusinessPctChange).toHaveBeenCalledWith(row, 60);
  });

  it("shows the saved business-use % again after the backend updates it", () => {
    const row = makeRow("1", "VERIZON WRLS", "-85.00", { category: "Phone & Data", business_pct: null });
    const { rerender } = render(
      <TxTable rows={[row]} categories={categories} saving={false} onCategoryChange={vi.fn()} onBusinessPctChange={vi.fn()} />,
    );
    const saved = { ...row, decision: { ...row.decision, business_pct: 60 } };
    rerender(
      <TxTable rows={[saved]} categories={categories} saving={false} onCategoryChange={vi.fn()} onBusinessPctChange={vi.fn()} />,
    );
    expect(screen.getByLabelText("Business-use percent for VERIZON WRLS")).toHaveValue(60);
  });

  it("shows a message when no rows match", () => {
    renderTable([]);
    expect(screen.getByText(/no rows match/i)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("puts the refund link next to the category", () => {
    renderTable([makeRow("1", "SHELL OIL REFUND", "20.00", { category: "Refund", refund_of: "Fuel" })]);
    const row = screen.getByText("SHELL OIL REFUND").closest("tr")!;
    expect(within(row).getByText("Reduces Fuel")).toBeInTheDocument();
  });
});
