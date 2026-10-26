"""Read a CSV or PDF statement into Transactions plus a file summary.

The steps, in order:
  1. Split the file into lines of cells (CSV lines, or the table rows of a PDF).
  2. Find the header line (it may sit under a few lines of account info).
  3. Take the data lines until a blank line or a "Total" / "Ending Balance" line.
  4. Turn each data line into a Transaction. A line we cannot read is skipped and reported.
  5. If more than 10% of lines could not be read, reject the whole file.
  6. Flag duplicates and rows outside the tax year, and build the summary.

We never pass a half-read file to the brain: we either read it properly or say why not.
"""

import csv
import hashlib
import io

from app.ingest.amounts import parse_date
from app.ingest.layouts import Layout, detect_layout, supported_layouts
from app.ingest.pdf_reader import PdfError, is_pdf, read_pdf_lines
from app.ingest.validate import flag_and_summarize
from app.models import FileSummary, SkippedRow, Transaction

HEADER_SEARCH_LINES = 15  # the header must be in the first 15 lines
MAX_BAD_ROW_SHARE = 0.10  # reject the file if more than 10% of rows are unreadable
FOOTER_WORDS = ("total", "ending balance", "closing balance", "beginning balance")


class IngestError(Exception):
    """The file cannot be used. `code` is for the API, `message` is for the user."""

    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def parse_statement(
    file_name: str, data: bytes, tax_year: int | None = None
) -> tuple[list[Transaction], FileSummary, int]:
    """Return (transactions, file summary, tax year used)."""
    # Step 1. A PDF gives us its table rows; a CSV gives us its lines. Same shape after this.
    if is_pdf(data):
        try:
            lines = read_pdf_lines(data)
        except PdfError as problem:
            raise IngestError(problem.code, problem.message) from problem
    else:
        lines = read_csv_lines(data)

    # Step 2
    header_index, layout = find_header(lines)
    column_names = [cell.strip().lower() for cell in lines[header_index]]
    junk_before_header = [line for line in lines[:header_index] if not is_blank(line)]

    # Step 3
    data_lines, footer_lines = split_data_and_footer(lines[header_index + 1 :])
    if not data_lines:
        raise IngestError("no_transactions", "The file has a header but no transaction rows.")

    # Step 4
    transactions: list[Transaction] = []
    skipped: list[SkippedRow] = []
    first_data_line_number = header_index + 2  # line numbers start at 1, after the header
    for offset, cells in enumerate(data_lines):
        line_number = first_data_line_number + offset
        try:
            tx = parse_line(cells, column_names, layout, file_name, line_number)
        except ValueError as problem:
            skipped.append(SkippedRow(row_number=line_number, reason=str(problem)))
            continue
        transactions.append(tx)

    # Step 5
    if len(skipped) > len(data_lines) * MAX_BAD_ROW_SHARE:
        first = skipped[0]
        raise IngestError(
            "too_many_bad_rows",
            f"{len(skipped)} of {len(data_lines)} rows could not be read (limit is 10%). "
            f"First problem: row {first.row_number}: {first.reason}",
            {"rows_skipped": [s.model_dump() for s in skipped]},
        )

    # Step 6
    summary, year_used = flag_and_summarize(
        transactions,
        file_name=file_name,
        layout=layout.name,
        skipped=skipped,
        junk_rows_before_header=len(junk_before_header),
        footer_rows=len(footer_lines),
        tax_year=tax_year,
    )
    return transactions, summary, year_used


def read_csv_lines(data: bytes) -> list[list[str]]:
    """Bytes -> list of lines, each a list of cells. Handles , ; tab or | as separator."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")  # older bank exports

    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel  # plain comma-separated
    return list(csv.reader(io.StringIO(text), dialect))


def find_header(lines: list[list[str]]) -> tuple[int, Layout]:
    for index, cells in enumerate(lines[:HEADER_SEARCH_LINES]):
        layout = detect_layout(cells)
        if layout:
            return index, layout
    raise IngestError(
        "unrecognized_layout",
        "Unrecognized statement layout. Supported layouts: " + "; ".join(supported_layouts()),
        {"supported_layouts": supported_layouts()},
    )


def split_data_and_footer(lines: list[list[str]]) -> tuple[list[list[str]], list[list[str]]]:
    """Data runs until the first blank or footer line. Everything after is footer."""
    for index, cells in enumerate(lines):
        if is_blank(cells) or is_footer(cells):
            footer = [line for line in lines[index:] if not is_blank(line)]
            return lines[:index], footer
    return lines, []


def parse_line(
    cells: list[str], column_names: list[str], layout: Layout, file_name: str, line_number: int
) -> Transaction:
    """One CSV line -> Transaction. Raises ValueError with a readable reason."""
    if len(cells) < len(layout.columns):
        raise ValueError("Too few columns")

    row = {}
    for name, value in zip(column_names, cells, strict=False):
        row[name] = value.strip()

    description = " ".join(row[layout.description_column].split())
    if not description:
        raise ValueError("Missing description")

    try:
        tx_date = parse_date(row[layout.date_column], layout.date_formats)
    except ValueError as problem:
        raise ValueError(f"Bad date: {problem}") from problem

    try:
        amount = layout.amount(row)
    except ValueError as problem:
        raise ValueError(f"Bad amount: {problem}") from problem
    if amount == 0:
        raise ValueError("Zero amount")

    bank_category = row.get(layout.category_column) if layout.category_column else None
    return Transaction(
        id=transaction_id(file_name, line_number),
        source_file=file_name,
        row_number=line_number,
        date=tx_date,
        raw_description=description,
        amount=amount,
        account=layout.account,
        bank_category=bank_category,
    )


def transaction_id(file_name: str, line_number: int) -> str:
    """Same file and line always give the same id."""
    return hashlib.sha1(f"{file_name}:{line_number}".encode()).hexdigest()[:12]


def is_blank(cells: list[str]) -> bool:
    return all(not cell.strip() for cell in cells)


def is_footer(cells: list[str]) -> bool:
    """A summary line such as "Ending Balance,,,3205.34".

    Only the first cell is checked: on a data line that cell is the date, so a
    shop called "TOTAL WINE" in the description is not mistaken for a footer.
    """
    first_cell = cells[0].strip().lower() if cells else ""
    return first_cell.startswith(FOOTER_WORDS)
