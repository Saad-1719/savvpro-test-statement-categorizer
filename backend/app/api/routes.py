"""HTTP routes. Thin: validate input, call services, shape output."""

import os
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response

from app.api.schemas import BulkTransactionPatch, RuleCreate, TransactionPatch, row
from app.config import settings
from app.errors import ServiceError
from app.ingest.pdf_reader import is_pdf
from app.reports.export import export_csv
from app.reports.review_groups import group_review_rows
from app.reports.totals import build_summary
from app.rules.loader import default_rules
from app.services import (
    add_user_rule,
    create_session,
    sessions,
    update_transaction,
    update_transactions,
)

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "rules_loaded": default_rules().rule_count}


@router.get("/categories")
def categories() -> list[dict]:
    return [c.model_dump() for c in default_rules().categories.values()]


async def _read_upload(upload: UploadFile) -> tuple[str, bytes]:
    """Read one uploaded file and check it is a real CSV or PDF of an allowed size."""
    name = os.path.basename(upload.filename or "statement.csv")
    is_csv_name = name.lower().endswith(".csv")
    is_pdf_name = name.lower().endswith(".pdf")
    if not is_csv_name and not is_pdf_name:
        raise ServiceError("unsupported_file", f"{name}: only .csv and .pdf files are supported.")

    data = await upload.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise ServiceError(
            "file_too_large", f"{name} is larger than {settings.max_upload_mb:g} MB.", 413
        )
    if not data.strip():
        raise ServiceError("empty_file", f"{name} is empty.")

    # The content must match the extension: a renamed file is refused, not guessed at.
    if is_pdf_name and not is_pdf(data):
        raise ServiceError("unsupported_file", f"{name} is not a real PDF file.")
    if is_csv_name and b"\x00" in data[:4096]:
        raise ServiceError("unsupported_file", f"{name} does not look like a text CSV file.")
    return name, data


def _rows(session) -> list[dict]:
    return [row(tx, session.decisions[tx.id]) for tx in session.transactions]


@router.post("/sessions", status_code=201)
async def upload(
    files: Annotated[list[UploadFile], File()],
    tax_year: Annotated[int | None, Form(ge=2000, le=2100)] = None,
) -> dict:
    if not files:
        raise ServiceError("no_files", "Upload at least one .csv file.")
    payload = [await _read_upload(f) for f in files]
    session = create_session(payload, tax_year)
    return {
        "session_id": session.id,
        "tax_year": session.tax_year,
        "file_summaries": jsonable_encoder(session.file_summaries),
        "transactions": _rows(session),
    }


@router.get("/sessions/{session_id}/transactions")
def transactions(
    session_id: str, status: str | None = None, category: str | None = None, q: str | None = None
) -> list[dict]:
    session = sessions.get(session_id)
    needle = q.upper().strip() if q else None
    result = []
    for tx in session.transactions:
        decision = session.decisions[tx.id]
        if status and decision.status != status:
            continue
        if category and category not in (decision.category, decision.suggestion):
            continue
        if needle and needle not in tx.raw_description.upper():
            continue
        result.append(row(tx, decision))
    return result


@router.get("/sessions/{session_id}/review")
def review_groups(session_id: str) -> list[dict]:
    session = sessions.get(session_id)
    return group_review_rows(session.transactions, session.decisions)


@router.patch("/sessions/{session_id}/transactions")
def patch_transactions(session_id: str, body: BulkTransactionPatch) -> list[dict]:
    """Change several rows at once (e.g. a whole review group). All of them, or none."""
    session = sessions.get(session_id)
    decisions = update_transactions(session, body.transaction_ids, body.category, body.business_pct)
    return [
        row(session.by_id[tx_id], decision)
        for tx_id, decision in zip(body.transaction_ids, decisions, strict=True)
    ]


@router.patch("/sessions/{session_id}/transactions/{tx_id}")
def patch_transaction(session_id: str, tx_id: str, body: TransactionPatch) -> dict:
    session = sessions.get(session_id)
    decision = update_transaction(session, tx_id, body.category, body.business_pct)
    return row(session.by_id[tx_id], decision)


@router.post("/sessions/{session_id}/rules", status_code=201)
def create_rule(session_id: str, body: RuleCreate) -> dict:
    session = sessions.get(session_id)
    rule, updated = add_user_rule(session, body.merchant_key, body.category, body.apply_to_existing)
    return {"rule": rule.model_dump(), "updated_count": updated}


@router.get("/sessions/{session_id}/summary")
def summary(session_id: str) -> dict:
    session = sessions.get(session_id)
    rules = default_rules()
    data = build_summary(session.transactions, session.decisions, rules.categories)
    data["tax_year"] = session.tax_year
    data["tax_form_name"] = rules.tax_form_name
    data["tax_form_note"] = rules.tax_form_note
    return jsonable_encoder(data, custom_encoder={Decimal: str})


@router.get("/sessions/{session_id}/export.csv")
def export(session_id: str) -> Response:
    session = sessions.get(session_id)
    return Response(
        content=export_csv(session.transactions, session.decisions),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="categorized_{session.tax_year}.csv"'
        },
    )
