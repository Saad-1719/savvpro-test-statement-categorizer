"""CSV export for the accountant: every row with its decision and reason."""

import csv
import io

from app.models import Decision, Transaction

COLUMNS = (
    "date",
    "description",
    "amount",
    "account",
    "status",
    "category",
    "refund_of",
    "business_pct",
    "suggestion",
    "reason",
    "rule_id",
    "decided_by",
    "flags",
    "source_file",
    "row_number",
)


def _safe(value: str) -> str:
    """Stop spreadsheet apps from running a cell as a formula."""
    return "'" + value if value[:1] in ("=", "+", "-", "@") and not _is_number(value) else value


def _is_number(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def export_csv(transactions: list[Transaction], decisions: dict[str, Decision]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(COLUMNS)
    for tx in sorted(transactions, key=lambda t: (t.date, t.source_file, t.row_number)):
        d = decisions[tx.id]
        row = [
            tx.date.isoformat(),
            tx.raw_description,
            str(tx.amount),
            tx.account,
            d.status,
            d.category or "",
            d.refund_of or "",
            "" if d.business_pct is None else str(d.business_pct),
            d.suggestion or "",
            d.reason,
            d.rule_id or "",
            d.decided_by,
            ";".join(tx.flags),
            tx.source_file,
            str(tx.row_number),
        ]
        writer.writerow([_safe(cell) for cell in row])
    return buffer.getvalue()
