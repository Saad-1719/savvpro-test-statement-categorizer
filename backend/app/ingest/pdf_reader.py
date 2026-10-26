"""Read the transaction table out of a text-based PDF statement.

The PDF table becomes the same thing a CSV gives us: a list of lines, each a list
of cells. From there the normal parser takes over (header, rows, footer, flags).

Two kinds of tables:
  - With drawn grid lines: pdfplumber finds the cells for us.
  - Without lines (common in bank PDFs): we place each word in a column ourselves,
    using where the column headers sit on the page. See `words_to_lines`.

Scanned PDFs (a picture of a page, no text inside) are not supported: they would
need OCR, which guesses characters. We say so instead of guessing.
"""

import io
import re

import pdfplumber

from app.ingest.layouts import LAYOUTS, Layout, detect_layout

MONEY_COLUMNS = {"amount", "balance", "debit", "credit"}  # right-aligned columns
FOOTER_WORDS = ("total", "ending balance", "closing balance", "beginning balance")

# An amount with cents: 64.99, -42.10, $1,387.90, (25.00), 15.00-
MONEY_WORD = re.compile(r"^[-(]?\$?-?[\d,]+\.\d{2}\)?-?$")

SAME_LINE_TOLERANCE = 3  # words whose tops differ by less than this are on one line
ALIGN_TOLERANCE = 2  # a word may start this far left of its header


class PdfError(ValueError):
    """The PDF cannot be read. `code` is for the API."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def is_pdf(data: bytes) -> bool:
    return data.startswith(b"%PDF-")


def read_pdf_lines(data: bytes) -> list[list[str]]:
    try:
        pdf = pdfplumber.open(io.BytesIO(data))
    except Exception as problem:  # pdfplumber raises many kinds of errors for broken files
        raise PdfError("bad_pdf", "The PDF file is damaged or not a real PDF.") from problem

    with pdf:
        has_text = False
        lines: list[list[str]] = []
        columns = None  # column positions, carried over to pages without a header
        for page in pdf.pages:
            if (page.extract_text() or "").strip():
                has_text = True

            tables = page.extract_tables()  # works when the table has grid lines
            if tables:
                for table in tables:
                    for row in table:
                        cells = clean_cells(row)
                        if any(cells):
                            lines.append(cells)
            else:
                page_lines, columns = words_to_lines(page.extract_words(), columns)
                lines.extend(page_lines)

    if not has_text:
        raise PdfError(
            "pdf_no_text",
            "This PDF has no text in it (it is probably a scan). "
            "Please download the CSV export from your bank instead.",
        )
    return drop_repeated_headers(lines)


def clean_cells(row: list[str | None]) -> list[str]:
    """Empty cells come back as None, and long cells can wrap onto two lines."""
    cells = []
    for cell in row:
        if cell is None:
            cells.append("")
        else:
            cells.append(" ".join(cell.split()))
    return cells


def drop_repeated_headers(lines: list[list[str]]) -> list[list[str]]:
    """A long statement repeats the column header at the top of every page. Keep the first."""
    kept = []
    seen_header = False
    for cells in lines:
        if detect_layout(cells):
            if seen_header:
                continue
            seen_header = True
        kept.append(cells)
    return kept


# ---------- Tables without grid lines ----------


class Column:
    """Where one column header sits on the page."""

    def __init__(self, name: str, left: float, right: float):
        self.name = name
        self.left = left
        self.right = right
        self.is_money = name in MONEY_COLUMNS


def words_to_lines(
    words: list[dict], columns: list[Column] | None
) -> tuple[list[list[str]], list[Column] | None]:
    """Turn the words on one page into lines of cells.

    Lines before the header (bank name, account info) and footer lines become one
    cell each, like they would in a CSV. Lines after the header are split into columns.
    """
    lines = []
    for line_words in group_into_lines(words):
        text = " ".join(word["text"] for word in line_words)

        header = find_header_columns(line_words)
        if header:
            columns = header
            lines.append([column.name for column in columns])
        elif columns is None or text.lower().startswith(FOOTER_WORDS):
            lines.append([text])
        else:
            lines.append(split_into_columns(line_words, columns))
    return lines, columns


def group_into_lines(words: list[dict]) -> list[list[dict]]:
    """Words that share (almost) the same height on the page form one line."""
    lines: list[list[dict]] = []
    for word in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if lines and abs(lines[-1][0]["top"] - word["top"]) < SAME_LINE_TOLERANCE:
            lines[-1].append(word)
        else:
            lines.append([word])
    for line in lines:
        line.sort(key=lambda w: w["x0"])  # left to right
    return lines


def find_header_columns(line_words: list[dict]) -> list[Column] | None:
    """If this line is a known header (e.g. "Posting Date Details Debit Credit"),
    return where each column header sits. Header names can be several words."""
    text = " ".join(word["text"] for word in line_words).lower()
    layout = layout_with_header_text(text)
    if layout is None:
        return None

    columns = []
    position = 0
    for name in layout.columns:
        word_count = len(name.split())
        header_words = line_words[position : position + word_count]
        columns.append(Column(name, header_words[0]["x0"], header_words[-1]["x1"]))
        position += word_count
    return columns


def layout_with_header_text(text: str) -> Layout | None:
    for layout in LAYOUTS:
        if text == " ".join(layout.columns):
            return layout
    return None


def split_into_columns(line_words: list[dict], columns: list[Column]) -> list[str]:
    """Put each word of a data line into a column.

    - An amount (e.g. 64.99) goes to the money column whose right edge is closest,
      because money columns are right-aligned.
    - Any other word goes to the last text column whose header starts at or before it,
      because text columns are left-aligned. A long description stays whole.
    """
    cells = {column.name: [] for column in columns}
    text_columns = [column for column in columns if not column.is_money]
    money_columns = [column for column in columns if column.is_money]

    for word in line_words:
        if money_columns and MONEY_WORD.match(word["text"]):
            target = min(money_columns, key=lambda column: abs(column.right - word["x1"]))
        else:
            target = text_columns[0]
            for column in text_columns:
                if word["x0"] >= column.left - ALIGN_TOLERANCE:
                    target = column
        cells[target.name].append(word["text"])

    return [" ".join(cells[column.name]) for column in columns]
