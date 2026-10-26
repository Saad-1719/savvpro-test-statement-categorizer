"""Flag duplicates and rows outside the tax year, and build the file summary."""

from collections import Counter
from decimal import Decimal

from app.models import FileSummary, SkippedRow, Transaction


def infer_tax_year(transactions: list[Transaction]) -> int:
    """The year most rows fall in; on a tie, the later year."""
    rows_per_year = Counter(tx.date.year for tx in transactions)
    best_year = None
    for year in sorted(rows_per_year):  # oldest to newest, so a tie goes to the later year
        if best_year is None or rows_per_year[year] >= rows_per_year[best_year]:
            best_year = year
    return best_year


def flag_and_summarize(
    transactions: list[Transaction],
    *,
    file_name: str,
    layout: str,
    skipped: list[SkippedRow],
    junk_rows_before_header: int,
    footer_rows: int,
    tax_year: int | None,
) -> tuple[FileSummary, int]:
    year = tax_year or infer_tax_year(transactions)

    seen: set[tuple] = set()
    for tx in transactions:
        signature = (tx.date, tx.raw_description.upper(), tx.amount, tx.account)
        if signature in seen:
            tx.flags.append("duplicate")
        seen.add(signature)
        if tx.date.year != year:
            tx.flags.append("outside_tax_year")

    counted = [tx for tx in transactions if not tx.flags]
    dates = [tx.date for tx in transactions]
    summary = FileSummary(
        file_name=file_name,
        layout=layout,
        rows_read=len(transactions),
        rows_skipped=skipped,
        junk_rows_before_header=junk_rows_before_header,
        footer_rows=footer_rows,
        duplicates=sum("duplicate" in tx.flags for tx in transactions),
        outside_tax_year=sum("outside_tax_year" in tx.flags for tx in transactions),
        date_from=min(dates, default=None),
        date_to=max(dates, default=None),
        money_in=sum((tx.amount for tx in counted if tx.amount > 0), Decimal("0")),
        money_out=sum((tx.amount for tx in counted if tx.amount < 0), Decimal("0")),
    )
    return summary, year
