import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ReviewQueue } from "../../components/ReviewQueue";
import { categories, makeGroup } from "../fixtures";

describe("ReviewQueue", () => {
  it("says so when nothing is left to review", () => {
    render(<ReviewQueue groups={[]} categories={categories} saving={false} onApply={vi.fn()} />);
    expect(screen.getByText(/nothing left to review/i)).toBeInTheDocument();
  });

  it("keeps Apply disabled until a category is chosen, then applies it to the group", async () => {
    const onApply = vi.fn();
    const group = makeGroup("JOES CAFE", ["t1", "t2"]);
    render(<ReviewQueue groups={[group]} categories={categories} saving={false} onApply={onApply} />);

    const apply = screen.getByRole("button", { name: "Apply" });
    expect(apply).toBeDisabled();

    await userEvent.selectOptions(screen.getByLabelText("Category for JOES CAFE"), "Personal");
    await userEvent.click(screen.getByLabelText(/always/i));
    await userEvent.click(apply);

    expect(onApply).toHaveBeenCalledWith(group, { category: "Personal", always: true, businessPct: undefined });
  });

  it("pre-selects the suggestion but does not apply it on its own", () => {
    const onApply = vi.fn();
    render(
      <ReviewQueue
        groups={[makeGroup("CHEVRON", ["t1"], { suggestion: "Fuel" })]}
        categories={categories}
        saving={false}
        onApply={onApply}
      />,
    );
    expect(screen.getByLabelText("Category for CHEVRON")).toHaveValue("Fuel");
    expect(onApply).not.toHaveBeenCalled();
  });

  it("asks for a business-use % for mixed-use categories and sends it", async () => {
    const onApply = vi.fn();
    const group = makeGroup("VERIZON", ["t1"]);
    render(<ReviewQueue groups={[group]} categories={categories} saving={false} onApply={onApply} />);

    await userEvent.selectOptions(screen.getByLabelText("Category for VERIZON"), "Phone & Data");
    const apply = screen.getByRole("button", { name: "Apply" });
    expect(apply).toBeDisabled();

    await userEvent.type(screen.getByPlaceholderText("%"), "60");
    await userEvent.click(apply);
    expect(onApply).toHaveBeenCalledWith(group, { category: "Phone & Data", always: false, businessPct: 60 });
  });

  it("disables everything while saving", () => {
    render(
      <ReviewQueue groups={[makeGroup("X", ["t1"], { suggestion: "Fuel" })]} categories={categories} saving onApply={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: "Saving…" })).toBeDisabled();
  });
});
