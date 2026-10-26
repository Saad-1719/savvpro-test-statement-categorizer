"""PDF statements: read the same as CSV, and fail clearly when they cannot be read."""

import io

import pytest
from reportlab.pdfgen import canvas

from app.brain.engine import categorize
from app.ingest.parser import IngestError, parse_statement
from eval.make_sample_pdf import render_statement_pdf
from tests.conftest import SAMPLE_DIR

INFO = ["First Federal Bank (fake)", "Account Number: XXXXXX4410"]
FOOTER = [["Ending Balance", "", "", "100.00"]]


def make_rows(count: int) -> list[list[str]]:
    return [
        [f"01/{(i % 28) + 1:02d}/2025", f"SHELL OIL {i}", "-10.00", "100.00"] for i in range(count)
    ]


def test_sample_pdf_reads_exactly_like_the_sample_csv() -> None:
    from_csv, csv_summary, _ = parse_statement(
        "s.csv", (SAMPLE_DIR / "first_federal_checking_2025.csv").read_bytes()
    )
    from_pdf, pdf_summary, _ = parse_statement(
        "s.pdf", (SAMPLE_DIR / "first_federal_checking_2025.pdf").read_bytes()
    )

    def simple(txs):
        return [(t.date, t.raw_description, t.amount, t.flags) for t in txs]

    assert simple(from_pdf) == simple(from_csv)
    assert pdf_summary.footer_rows == csv_summary.footer_rows == 2

    csv_decisions = [(d.status, d.category) for d in categorize(from_csv)]
    pdf_decisions = [(d.status, d.category) for d in categorize(from_pdf)]
    assert pdf_decisions == csv_decisions


def test_multi_page_pdf_skips_the_repeated_header() -> None:
    data = render_statement_pdf(INFO, make_rows(120), FOOTER)
    txs, summary, _ = parse_statement("long.pdf", data)
    assert len(txs) == 120
    assert summary.rows_skipped == []


def test_pdf_table_without_grid_lines() -> None:
    data = render_statement_pdf(INFO, make_rows(5), FOOTER, grid=False)
    txs, _, _ = parse_statement("plain.pdf", data)
    assert [t.raw_description for t in txs] == [f"SHELL OIL {i}" for i in range(5)]


def test_scanned_pdf_is_refused_with_a_clear_reason() -> None:
    buffer = io.BytesIO()
    page = canvas.Canvas(buffer)
    page.rect(50, 50, 200, 100, fill=1)  # a picture only, no text, like a scan
    page.save()
    with pytest.raises(IngestError) as err:
        parse_statement("scan.pdf", buffer.getvalue())
    assert err.value.code == "pdf_no_text"


def test_broken_pdf_is_refused() -> None:
    with pytest.raises(IngestError) as err:
        parse_statement("broken.pdf", b"%PDF-1.4 this is not really a pdf")
    assert err.value.code == "bad_pdf"


def test_pdf_with_unknown_table_layout() -> None:
    data = render_statement_pdf(INFO, [["01/02/2025", "X", "1"]], [], header=["When", "What", "$"])
    with pytest.raises(IngestError) as err:
        parse_statement("other.pdf", data)
    assert err.value.code == "unrecognized_layout"
