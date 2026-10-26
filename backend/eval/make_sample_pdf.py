"""Build a fake PDF bank statement from a fake CSV statement.

We may not use real bank statements, so we make our own PDF that looks like one:
bank name and account info at the top, the transaction table, totals at the bottom.

    python -m eval.make_sample_pdf
    (reads  sample_data/first_federal_checking_2025.csv,
     writes sample_data/first_federal_checking_2025.pdf)
"""

import csv
import io
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample_data"
SOURCE = SAMPLE_DIR / "first_federal_checking_2025.csv"
TARGET = SAMPLE_DIR / "first_federal_checking_2025.pdf"

HEADER = ["Date", "Description", "Amount", "Balance"]


def render_statement_pdf(
    info_lines: list[str],
    rows: list[list[str]],
    footer_rows: list[list[str]],
    header: list[str] = HEADER,
    grid: bool = True,
) -> bytes:
    """Draw a statement: info lines, then one table (header, rows, footer rows).

    `grid=False` draws the table without lines, like many real bank PDFs.
    """
    styles = getSampleStyleSheet()
    story = [Paragraph(info_lines[0], styles["Title"])]
    for line in info_lines[1:]:
        story.append(Paragraph(line, styles["Normal"]))
    story.append(Spacer(1, 12))

    table = Table([header, *rows, *footer_rows], repeatRows=1)  # header repeats on each page
    style = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
    ]
    if grid:
        style.append(("GRID", (0, 0), (-1, -1), 0.5, colors.grey))
    table.setStyle(TableStyle(style))
    story.append(table)

    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=LETTER, title="Fake bank statement").build(story)
    return buffer.getvalue()


def read_sample_csv(path: Path) -> tuple[list[str], list[list[str]], list[list[str]]]:
    """Split the sample CSV into (info lines, transaction rows, footer rows)."""
    with path.open(encoding="utf-8") as f:
        lines = list(csv.reader(f))
    header_index = next(i for i, cells in enumerate(lines) if cells[:1] == ["Date"])
    info = [cells[0] for cells in lines[:header_index] if cells]
    body = [cells for cells in lines[header_index + 1 :] if any(cells)]
    rows = [cells for cells in body if not cells[0].lower().startswith(("ending", "total"))]
    footer = [cells for cells in body if cells[0].lower().startswith(("ending", "total"))]
    return info, rows, footer


def main() -> None:
    info, rows, footer = read_sample_csv(SOURCE)
    TARGET.write_bytes(render_statement_pdf(info, rows, footer))
    print(f"wrote {TARGET} ({len(rows)} transactions)")


if __name__ == "__main__":
    main()
