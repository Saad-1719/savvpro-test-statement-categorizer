"""Upload -> review -> rule -> patch -> summary -> export through the HTTP API."""

import csv
import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import SAMPLE_DIR

client = TestClient(app)


def upload(name: str, data: bytes):
    return client.post("/api/sessions", files={"files": (name, data, "text/csv")})


@pytest.fixture
def session_id() -> str:
    data = (SAMPLE_DIR / "first_federal_checking_2025.csv").read_bytes()
    response = upload("sample.csv", data)
    assert response.status_code == 201
    return response.json()["session_id"]


def test_health_reports_rules() -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["rules_loaded"] > 0


def test_categories() -> None:
    categories = {c["name"]: c for c in client.get("/api/categories").json()}
    assert categories["Phone & Data"]["mixed_use"] is True
    assert categories["Fuel"]["tax_line"] == "9"


def test_full_journey(session_id: str) -> None:
    base = f"/api/sessions/{session_id}"

    groups = client.get(f"{base}/review").json()
    assert groups and all(g["count"] >= 1 for g in groups)
    assert not client.get(f"{base}/summary").json()["is_final"]

    # Fix every review group with an "always" rule, the way the UI does.
    for group in groups:
        category = group["suggestion"] or "Personal"
        response = client.post(
            f"{base}/rules", json={"merchant_key": group["merchant_key"], "category": category}
        )
        assert response.status_code == 201
    assert client.get(f"{base}/review").json() == []

    # Phone & Data needs a business-use %.
    phone = client.get(f"{base}/transactions", params={"category": "Phone & Data"}).json()
    for row in phone:
        response = client.patch(f"{base}/transactions/{row['id']}", json={"business_pct": 50})
        assert response.status_code == 200
        assert response.json()["decision"]["business_pct"] == 50

    summary = client.get(f"{base}/summary").json()
    assert summary["is_final"], summary
    assert summary["unreviewed_amount"] == "0.00"

    export = client.get(f"{base}/export.csv")
    assert export.status_code == 200
    assert "attachment" in export.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(export.text)))
    assert rows and {"category", "status", "reason", "rule_id"} <= set(rows[0])
    assert not any(r["status"] == "review" for r in rows)


def test_patch_changes_auto_row(session_id: str) -> None:
    base = f"/api/sessions/{session_id}"
    fuel = client.get(f"{base}/transactions", params={"category": "Fuel", "status": "auto"}).json()
    response = client.patch(f"{base}/transactions/{fuel[0]['id']}", json={"category": "Personal"})
    decision = response.json()["decision"]
    assert (decision["category"], decision["decided_by"]) == ("Personal", "user")


def test_filters(session_id: str) -> None:
    base = f"/api/sessions/{session_id}"
    rows = client.get(f"{base}/transactions", params={"q": "uber"}).json()
    assert rows and all("UBER" in r["raw_description"].upper() for r in rows)
    rows = client.get(f"{base}/transactions", params={"status": "excluded"}).json()
    assert rows and all(r["decision"]["status"] == "excluded" for r in rows)


@pytest.mark.parametrize(
    ("name", "data", "status", "code"),
    [
        ("x.txt", b"Date,Description,Amount,Balance\n", 422, "unsupported_file"),
        ("x.pdf", b"Date,Description,Amount,Balance\n", 422, "unsupported_file"),
        ("x.pdf", b"%PDF-1.4 broken", 422, "bad_pdf"),
        ("x.csv", b"", 422, "empty_file"),
        ("x.csv", b"a,b\n1,2\n", 422, "unrecognized_layout"),
        ("x.csv", b"Date,Description,Amount,Balance\nnope,X,abc,1\n", 422, "too_many_bad_rows"),
    ],
)
def test_upload_errors_have_one_shape(name, data, status, code) -> None:
    response = upload(name, data)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_file_too_large(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.MAX_UPLOAD_BYTES", 10)
    response = upload("x.csv", b"Date,Description,Amount,Balance\n")
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_bad_category_and_pct(session_id: str) -> None:
    base = f"/api/sessions/{session_id}"
    tx_id = client.get(f"{base}/transactions").json()[0]["id"]
    bad = client.patch(f"{base}/transactions/{tx_id}", json={"category": "Snacks"})
    assert bad.json()["error"]["code"] == "invalid_category"
    fuel = client.get(f"{base}/transactions", params={"category": "Fuel"}).json()[0]["id"]
    bad = client.patch(f"{base}/transactions/{fuel}", json={"business_pct": 50})
    assert bad.json()["error"]["code"] == "business_pct_not_allowed"


def test_unknown_session() -> None:
    response = client.get("/api/sessions/nope/summary")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "session_not_found"


def test_pdf_upload_gives_the_same_results_as_csv() -> None:
    csv_rows = upload("s.csv", (SAMPLE_DIR / "first_federal_checking_2025.csv").read_bytes())
    pdf_rows = upload("s.pdf", (SAMPLE_DIR / "first_federal_checking_2025.pdf").read_bytes())
    assert pdf_rows.status_code == 201

    def simple(response):
        return [
            (r["raw_description"], r["amount"], r["decision"]["status"], r["decision"]["category"])
            for r in response.json()["transactions"]
        ]

    assert simple(pdf_rows) == simple(csv_rows)


def test_summary_groups_totals_by_tax_form_line(session_id: str) -> None:
    summary = client.get(f"/api/sessions/{session_id}/summary").json()
    assert "Schedule C" in summary["tax_form_name"]  # the form is data, not code
    assert summary["tax_form_note"]
    lines = {line["line"]: line for line in summary["tax_form_lines"]}
    assert lines["1"]["label"] == "Gross receipts"
    car = [t for t in summary["totals"] if t["tax_line"] == "9" and t["deductible_amount"]]
    car_total = sum(float(t["deductible_amount"]) for t in car)
    assert float(lines["9"]["amount"]) == pytest.approx(car_total)
