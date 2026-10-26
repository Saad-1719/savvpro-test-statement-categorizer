"use client";

// The start screen: drop a CSV or PDF statement, click "Choose file", or try one of the sample statements.

import { useRef, useState } from "react";
import { FileIcon, UploadIcon } from "./icons";

// Sample statements in public/samples (copied there from ../sample_data by scripts/copy-samples.mjs).
// Each one exists as both .csv and .pdf.
const SAMPLES = [
  { file: "first_federal_checking_2025", title: "Demo statement", detail: "30 rows with the tricky cases" },
  { file: "driver_full_year_2025", title: "Full year", detail: "300 rows across 2025" },
  { file: "metro_bank_checking_2025", title: "Debit / Credit bank", detail: "Separate money-in and money-out columns" },
];

const STEPS = [
  { title: "Upload", text: "A bank statement as CSV or PDF. It is read in memory and never stored." },
  { title: "Review", text: "Rules sort each row. Anything the app is not sure about goes to Needs Review." },
  { title: "Export", text: "Fix the unsure rows, then download totals for your accountant." },
];

const MAX_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB

interface Props {
  busy: boolean;
  onUpload: (file: File, taxYear?: number) => void;
  onError: (message: string) => void;
}

export function UploadZone({ busy, onUpload, onError }: Props) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [taxYear, setTaxYear] = useState("");

  const thisYear = new Date().getFullYear();
  const yearOptions = [thisYear, thisYear - 1, thisYear - 2, thisYear - 3];

  // Checks the file, then hands it to the page. Phase 1 takes one file at a time.
  function uploadFile(file: File | undefined) {
    if (!file) return;
    const name = file.name.toLowerCase();
    if (!name.endsWith(".csv") && !name.endsWith(".pdf")) {
      onError(`"${file.name}" is not a CSV or PDF file.`);
      return;
    }
    if (file.size > MAX_SIZE_BYTES) {
      onError(`"${file.name}" is larger than 5 MB.`);
      return;
    }
    onUpload(file, taxYear ? Number(taxYear) : undefined);
  }

  async function uploadSample(fileName: string) {
    const res = await fetch(`/samples/${fileName}`);
    if (!res.ok) {
      onError("Could not load the sample file. Run `npm run dev` so it is copied into public/samples.");
      return;
    }
    const content = await res.blob();
    uploadFile(new File([content], fileName, { type: content.type }));
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8 py-6">
      <div className="text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Sort your statement for tax time</h1>
        <p className="mx-auto mt-2 max-w-xl text-slate-600">
          For rideshare and delivery drivers. Every transaction gets a tax category and a reason. When the app is not
          sure, it asks you instead of guessing.
        </p>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            if (!busy) uploadFile(e.dataTransfer.files[0]);
          }}
          className={
            "flex flex-col items-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors " +
            (dragging ? "border-indigo-500 bg-indigo-50" : "border-slate-300 bg-slate-50")
          }
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-indigo-100 text-indigo-600">
            <UploadIcon className="h-6 w-6" />
          </div>
          <p className="mt-3 text-base font-medium text-slate-900">
            {busy ? "Reading statement…" : "Drop your bank statement here"}
          </p>
          <p className="mt-1 text-sm text-slate-500">CSV or text-based PDF, up to 5 MB. Scanned PDFs can&apos;t be read.</p>
          <button
            type="button"
            disabled={busy}
            onClick={() => fileInput.current?.click()}
            className="mt-4 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
          >
            {busy ? "Working…" : "Choose file"}
          </button>
          <input
            ref={fileInput}
            type="file"
            accept=".csv,.pdf,text/csv,application/pdf"
            className="hidden"
            onChange={(e) => {
              uploadFile(e.target.files?.[0]);
              e.target.value = ""; // lets the user pick the same file again
            }}
          />
        </div>

        <label className="mt-4 flex items-center justify-center gap-2 text-sm text-slate-600">
          Tax year
          <select
            value={taxYear}
            onChange={(e) => setTaxYear(e.target.value)}
            className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm"
          >
            <option value="">Detect from file</option>
            {yearOptions.map((year) => (
              <option key={year} value={year}>
                {year}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section>
        <h2 className="text-sm font-semibold text-slate-700">No statement handy? Try a fake one</h2>
        <div className="mt-2 grid gap-3 sm:grid-cols-3">
          {SAMPLES.map((sample) => (
            <div key={sample.file} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-2 text-slate-900">
                <FileIcon className="h-4 w-4 text-slate-400" />
                <p className="text-sm font-medium">{sample.title}</p>
              </div>
              <p className="mt-1 text-xs text-slate-500">{sample.detail}</p>
              <div className="mt-3 flex gap-2">
                <SampleButton label="CSV" disabled={busy} onClick={() => uploadSample(`${sample.file}.csv`)} title={sample.title} />
                <SampleButton label="PDF" disabled={busy} onClick={() => uploadSample(`${sample.file}.pdf`)} title={sample.title} />
              </div>
            </div>
          ))}
        </div>
      </section>

      <ol className="grid gap-3 sm:grid-cols-3">
        {STEPS.map((step, index) => (
          <li key={step.title} className="flex gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-200 text-xs font-semibold text-slate-700">
              {index + 1}
            </span>
            <div>
              <p className="text-sm font-medium text-slate-900">{step.title}</p>
              <p className="text-xs text-slate-500">{step.text}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

interface SampleButtonProps {
  label: string;
  title: string;
  disabled: boolean;
  onClick: () => void;
}

function SampleButton({ label, title, disabled, onClick }: SampleButtonProps) {
  return (
    <button
      type="button"
      aria-label={`Try ${title} ${label}`}
      disabled={disabled}
      onClick={onClick}
      className="flex-1 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:border-indigo-400 hover:bg-indigo-50 hover:text-indigo-700 disabled:opacity-50"
    >
      {label}
    </button>
  );
}
