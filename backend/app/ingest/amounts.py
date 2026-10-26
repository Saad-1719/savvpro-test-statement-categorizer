"""Turn the date and amount text from a statement into real values."""

import re
from datetime import date, datetime
from decimal import Decimal

# Date formats used by US banks: 01/18/2025, 2025-01-18, 18 Jan 2025.
# Each bank layout says which formats it uses (see layouts.py). A layout never lists
# both 01/02 orders (month/day and day/month), so a date can't be read the wrong way round.
US_DATE_FORMATS = ("%m/%d/%Y", "%Y-%m-%d", "%d %b %Y")

# Digits with up to 2 decimals, e.g. "1234" or "1234.50".
MONEY = re.compile(r"\d+(\.\d{1,2})?")


def parse_date(text: str, formats: tuple[str, ...] = US_DATE_FORMATS) -> date:
    value = " ".join(text.split())
    for date_format in formats:
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            pass  # not this format, try the next one
    raise ValueError(f"unrecognized date {text!r}")


def parse_amount(text: str) -> Decimal:
    """Read an amount and return it signed: negative means money out.

    Banks write "money out" in different ways, and we accept all of them:
        -18.40    (25.00)    15.00-    -$850.00    $-850.00
    Commas and the $ sign are ignored: "$1,234.50" -> 1234.50.
    """
    value = text.strip().replace(",", "").replace(" ", "")
    if not value:
        raise ValueError("empty amount")

    minus_signs = 0

    if value.startswith("(") and value.endswith(")"):  # (25.00)
        minus_signs += 1
        value = value[1:-1]

    if value.endswith("-"):  # 15.00-
        minus_signs += 1
        value = value[:-1]

    value = value.removeprefix("+")

    if value.startswith("-"):  # -18.40 or -$850.00
        minus_signs += 1
        value = value[1:]

    value = value.removeprefix("$")

    if value.startswith("-"):  # $-850.00
        minus_signs += 1
        value = value[1:]

    # "--5" or "(5.00)-" is not a format any bank uses, so we refuse to guess.
    if minus_signs > 1:
        raise ValueError(f"amount has more than one minus sign: {text!r}")
    if not MONEY.fullmatch(value):
        raise ValueError(f"unrecognized amount {text!r}")

    amount = Decimal(value)
    if minus_signs == 1:
        return -amount
    return amount
