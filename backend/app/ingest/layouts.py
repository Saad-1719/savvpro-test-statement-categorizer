"""Bank layout profiles (all fake banks) and header detection.

Adding a layout means adding a profile here plus a test; the parser does not change.
"""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from app.ingest.amounts import parse_amount


@dataclass(frozen=True)
class Layout:
    name: str
    columns: tuple[str, ...]  # header signature, lower-case, in order
    account: str
    date_column: str
    description_column: str
    amount: Callable[[dict[str, str]], Decimal]  # signed: negative = money out
    category_column: str | None = None


def _signed_amount(row: dict[str, str]) -> Decimal:
    return parse_amount(row["amount"])


def _debit_credit(row: dict[str, str]) -> Decimal:
    """Separate columns, both written as positive numbers."""
    debit = abs(parse_amount(row["debit"])) if row.get("debit") else Decimal("0")
    credit = abs(parse_amount(row["credit"])) if row.get("credit") else Decimal("0")
    if debit and credit:
        raise ValueError("both debit and credit are filled")
    return credit - debit


LAYOUTS: tuple[Layout, ...] = (
    Layout(
        name="first_federal_checking",
        columns=("date", "description", "amount", "balance"),
        account="checking",
        date_column="date",
        description_column="description",
        amount=_signed_amount,
    ),
    Layout(
        name="metro_bank_checking",
        columns=("posting date", "details", "debit", "credit"),
        account="checking",
        date_column="posting date",
        description_column="details",
        amount=_debit_credit,
    ),
)


def _normalize_header(cells: list[str]) -> tuple[str, ...]:
    return tuple(cell.strip().lower() for cell in cells if cell.strip())


def detect_layout(cells: list[str]) -> Layout | None:
    header = _normalize_header(cells)
    for layout in LAYOUTS:
        if header == layout.columns:
            return layout
    return None


def supported_layouts() -> list[str]:
    return [f"{layout.name} ({', '.join(layout.columns)})" for layout in LAYOUTS]
