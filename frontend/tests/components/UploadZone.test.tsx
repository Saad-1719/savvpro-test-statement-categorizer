import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { UploadZone } from "../../components/UploadZone";

function fileInput(): HTMLInputElement {
  return document.querySelector('input[type="file"]') as HTMLInputElement;
}

describe("UploadZone", () => {
  it("uploads a CSV with the chosen tax year", async () => {
    const onUpload = vi.fn();
    render(<UploadZone busy={false} onUpload={onUpload} onError={vi.fn()} />);
    const year = String(new Date().getFullYear() - 1);
    await userEvent.selectOptions(screen.getByLabelText(/tax year/i), year);

    const file = new File(["Date,Description,Amount,Balance"], "statement.csv", { type: "text/csv" });
    await userEvent.upload(fileInput(), file);
    expect(onUpload).toHaveBeenCalledWith(file, Number(year));
  });

  it("rejects files that are not CSV or PDF", () => {
    const onUpload = vi.fn();
    const onError = vi.fn();
    render(<UploadZone busy={false} onUpload={onUpload} onError={onError} />);
    // fireEvent skips the input's accept filter, like a drag-and-drop would.
    fireEvent.change(fileInput(), { target: { files: [new File(["hi"], "notes.txt")] } });
    expect(onError).toHaveBeenCalledWith('"notes.txt" is not a CSV or PDF file.');
    expect(onUpload).not.toHaveBeenCalled();
  });

  it("rejects files over 5 MB", () => {
    const onError = vi.fn();
    render(<UploadZone busy={false} onUpload={vi.fn()} onError={onError} />);
    const big = new File([new Uint8Array(5 * 1024 * 1024 + 1)], "big.csv");
    fireEvent.change(fileInput(), { target: { files: [big] } });
    expect(onError).toHaveBeenCalledWith('"big.csv" is larger than 5 MB.');
  });

  it("loads a sample statement", async () => {
    const onUpload = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Date,Description,Amount,Balance")));
    render(<UploadZone busy={false} onUpload={onUpload} onError={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Try Demo statement PDF" }));
    expect(fetch).toHaveBeenCalledWith("/samples/first_federal_checking_2025.pdf");
    expect(onUpload.mock.calls[0][0].name).toBe("first_federal_checking_2025.pdf");
  });

  it("disables the buttons while busy", () => {
    render(<UploadZone busy onUpload={vi.fn()} onError={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Working…" })).toBeDisabled();
  });
});
