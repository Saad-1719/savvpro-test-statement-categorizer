"""Build fake statements for trying the app by hand: good files and broken files.

    python -m eval.make_test_files      (or: make samples)

Good files (sample_data/):
    metro_bank_checking_2025.csv / .pdf   Debit/Credit layout; the PDF has no grid lines
    driver_full_year_2025.csv / .pdf      ~300 rows for a whole year; the PDF has several pages

Broken files (sample_data/broken/), each must be refused with a clear message:
    unknown_layout.csv, header_only.csv, too_many_bad_rows.csv, empty.csv,
    scanned_statement.pdf, renamed_text.pdf

Everything is fake and seeded, so the files are identical on every run.
"""

import csv
import io
from decimal import Decimal
from pathlib import Path

from reportlab.pdfgen import canvas

from eval.generate_data import generate
from eval.make_sample_pdf import SAMPLE_DIR, render_statement_pdf

BROKEN_DIR = SAMPLE_DIR / "broken"

METRO_INFO = [
    "Metro Bank (fake sample)",
    "Customer: Ali Driver (sample)",
    "Account: XXXXXX7702",
    "Period: 01/01/2025 - 03/31/2025",
]
METRO_HEADER = ["Posting Date", "Details", "Debit", "Credit"]
# (date, details, debit, credit): both written as positive numbers, one of them empty.
METRO_ROWS = [
    ("01/02/2025", "LYFT DRIVER PAYOUT", "", "388.20"),
    ("01/03/2025", "CHEVRON 0091", "46.80", ""),
    ("01/05/2025", "UBER *TRIP HELP.UBER.COM", "22.15", ""),
    ("01/07/2025", "FASTRAK CSC", "18.00", ""),
    ("01/09/2025", "DOORDASH DASHER PAYOUT", "", "301.44"),
    ("01/10/2025", "AUTOZONE 4471", "64.99", ""),
    ("01/12/2025", "AMAZON MKTPL*AB12CD3", "29.99", ""),
    ("01/14/2025", "T-MOBILE AUTOPAY", "70.00", ""),
    ("01/15/2025", "ONLINE TRANSFER TO SAVINGS", "300.00", ""),
    ("01/16/2025", "AUTOZONE 4471 REFUND", "", "12.00"),
    ("01/18/2025", "PROGRESSIVE INS", "121.50", ""),
    ("01/20/2025", "TST* TACO TRUCK 22", "11.25", ""),
    ("01/22/2025", "VALERO 7781 CA", "131.40", ""),
    ("01/24/2025", "LYFT BONUS PAYOUT", "", "45.00"),
    ("01/27/2025", "MONTHLY MAINTENANCE FEE", "12.00", ""),
    ("02/01/2025", "UBER TECHNOLOGIES PAYOUT", "", "512.75"),
    ("02/03/2025", "PARKMOBILE 2231", "4.50", ""),
    ("02/05/2025", "KROGER FUEL CENTER 0412", "38.60", ""),
    ("02/08/2025", "ZELLE FROM SAM", "", "60.00"),
    ("02/10/2025", "DISCOUNT TIRE 0099", "412.00", ""),
    ("02/12/2025", "UBER *EATS", "31.80", ""),
    ("02/15/2025", "COSTCO WHSE 0123", "142.10", ""),
    ("02/18/2025", "ATM FEE", "3.00", ""),
    ("02/20/2025", "LYFT EXPRESS PAY FEE", "1.50", ""),
    ("02/24/2025", "SHELL OIL 57442 TX", "41.20", ""),
    ("03/01/2025", "DOORDASH DASHER PAYOUT", "", "277.60"),
    ("03/04/2025", "PEP BOYS 112", "89.95", ""),
    ("03/07/2025", "PAYPAL *PHONEMOUNTCO", "24.99", ""),
    ("03/10/2025", "GREEN LEAF BARBER", "25.00", ""),
    ("03/14/2025", "SUNPASS REPLENISH", "20.00", ""),
]


def write_csv(path: Path, info: list[str], header: list[str], rows: list, footer: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for line in info:
            writer.writerow([line])
        writer.writerow([])
        writer.writerow(header)
        writer.writerows(rows)
        writer.writerow([])
        writer.writerows(footer)


def metro_bank_files() -> None:
    rows = [list(row) for row in METRO_ROWS]
    footer = [["Total Debits", "", "", ""], ["Total Credits", "", "", ""]]
    write_csv(SAMPLE_DIR / "metro_bank_checking_2025.csv", METRO_INFO, METRO_HEADER, rows, footer)
    pdf = render_statement_pdf(METRO_INFO, rows, [], header=METRO_HEADER, grid=False)
    (SAMPLE_DIR / "metro_bank_checking_2025.pdf").write_bytes(pdf)


def full_year_files() -> None:
    """A whole year from the seeded eval generator, with a running balance."""
    generated = sorted(generate(seed=7, rows=300), key=lambda row: row["date"])
    balance = Decimal("2500.00")
    rows = []
    for item in generated:
        balance += Decimal(item["amount"])
        year, month, day = item["date"].split("-")
        rows.append([f"{month}/{day}/{year}", item["description"], item["amount"], str(balance)])

    info = [
        "First Federal Bank (fake sample)",
        "Account Holder: Ali Driver (sample)",
        "Account Number: XXXXXX4410",
        "Statement Period: 01/01/2025 - 12/31/2025",
    ]
    footer = [
        ["Ending Balance", "", "", str(balance)],
        ["Total Transactions", "", "", str(len(rows))],
    ]
    header = ["Date", "Description", "Amount", "Balance"]
    write_csv(SAMPLE_DIR / "driver_full_year_2025.csv", info, header, rows, footer)
    pdf = render_statement_pdf(info, rows, footer, header=header)
    (SAMPLE_DIR / "driver_full_year_2025.pdf").write_bytes(pdf)


def broken_files() -> None:
    BROKEN_DIR.mkdir(parents=True, exist_ok=True)

    # Columns we do not know.
    (BROKEN_DIR / "unknown_layout.csv").write_text(
        "When,What,How Much\n01/03/2025,SHELL OIL,-42.10\n", encoding="utf-8"
    )
    # A header but no transactions.
    (BROKEN_DIR / "header_only.csv").write_text(
        "Date,Description,Amount,Balance\n", encoding="utf-8"
    )
    # 4 of 10 rows unreadable: above the 10% limit, so the whole file is refused.
    good = "".join(f"01/{day:02d}/2025,SHELL OIL,-40.00,100.00\n" for day in range(1, 7))
    bad = "31/31/2025,BAD DATE,-1.00,1\n01/08/2025,BAD AMOUNT,abc,1\n" * 2
    (BROKEN_DIR / "too_many_bad_rows.csv").write_text(
        "Date,Description,Amount,Balance\n" + good + bad, encoding="utf-8"
    )
    # Nothing in it.
    (BROKEN_DIR / "empty.csv").write_text("", encoding="utf-8")

    # A "scan": a PDF that only has a picture, no text.
    buffer = io.BytesIO()
    page = canvas.Canvas(buffer)
    page.setFillGray(0.85)
    page.rect(60, 400, 480, 300, fill=1)
    page.save()
    (BROKEN_DIR / "scanned_statement.pdf").write_bytes(buffer.getvalue())

    # A CSV renamed to .pdf.
    (BROKEN_DIR / "renamed_text.pdf").write_text(
        "Date,Description,Amount,Balance\n01/03/2025,X,-1.00,1\n", encoding="utf-8"
    )


def main() -> None:
    metro_bank_files()
    full_year_files()
    broken_files()
    print(f"wrote sample files to {SAMPLE_DIR} and {BROKEN_DIR}")


if __name__ == "__main__":
    main()
