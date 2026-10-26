"""Every sample file in sample_data/ behaves as sample_data/README.md says."""

import pytest
from fastapi.testclient import TestClient

from app.brain.engine import categorize
from app.ingest.parser import parse_statement
from app.main import app
from tests.conftest import SAMPLE_DIR

client = TestClient(app)

STATEMENTS = ["first_federal_checking_2025", "metro_bank_checking_2025", "driver_full_year_2025"]


@pytest.mark.parametrize("name", STATEMENTS)
def test_pdf_and_csv_give_the_same_result(name: str) -> None:
    from_csv, _, _ = parse_statement("s.csv", (SAMPLE_DIR / f"{name}.csv").read_bytes())
    from_pdf, _, _ = parse_statement("s.pdf", (SAMPLE_DIR / f"{name}.pdf").read_bytes())

    def rows(txs):
        return [(t.date, t.raw_description, t.amount, t.flags) for t in txs]

    def decisions(txs):
        return [(d.status, d.category, d.reason) for d in categorize(txs)]

    assert rows(from_pdf) == rows(from_csv)
    assert decisions(from_pdf) == decisions(from_csv)


@pytest.mark.parametrize(
    ("file_name", "code"),
    [
        ("unknown_layout.csv", "unrecognized_layout"),
        ("header_only.csv", "no_transactions"),
        ("too_many_bad_rows.csv", "too_many_bad_rows"),
        ("empty.csv", "empty_file"),
        ("scanned_statement.pdf", "pdf_no_text"),
        ("renamed_text.pdf", "unsupported_file"),
    ],
)
def test_broken_files_are_refused_with_a_clear_reason(file_name: str, code: str) -> None:
    data = (SAMPLE_DIR / "broken" / file_name).read_bytes()
    response = client.post("/api/sessions", files={"files": (file_name, data)})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == code
    assert error["message"]
