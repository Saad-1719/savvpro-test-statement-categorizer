import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Totals } from "../../components/Totals";
import { makeSummary } from "../fixtures";

describe("Totals", () => {
  it("is a Draft until the backend says the totals are final", () => {
    const { rerender } = render(<Totals summary={makeSummary()} exportUrl="/export.csv" />);
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByText(/draft until every row is reviewed/i)).toBeInTheDocument();

    rerender(<Totals summary={makeSummary({ is_final: true, unreviewed_count: 0 })} exportUrl="/export.csv" />);
    expect(screen.getByText("Final")).toBeInTheDocument();
    expect(screen.queryByText(/draft until/i)).not.toBeInTheDocument();
  });

  it("shows the deductible part of a mixed-use category", () => {
    render(<Totals summary={makeSummary()} exportUrl="/export.csv" />);
    expect(screen.getByText("Deductible: $51.00")).toBeInTheDocument();
  });

  it("switches to the tax-form view", async () => {
    render(<Totals summary={makeSummary()} exportUrl="/export.csv" />);
    const button = screen.getByRole("button", { name: "By tax-form line" });
    expect(button).toHaveAttribute("aria-pressed", "false");

    await userEvent.click(button);
    expect(button).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Schedule C (Form 1040)")).toBeInTheDocument();
    expect(screen.getByText("Line 9")).toBeInTheDocument();
    expect(screen.getByText("Informational only.")).toBeInTheDocument();
  });

  it("links the export button to the CSV download", () => {
    render(<Totals summary={makeSummary()} exportUrl="http://api/export.csv" />);
    expect(screen.getByRole("link", { name: /export csv/i })).toHaveAttribute("href", "http://api/export.csv");
  });
});
