"""Clean a raw bank description into a short "merchant key" used for matching.

Examples:
    SHELL OIL 57442 TX   -> SHELL OIL      (store number and state dropped)
    SQ *JOES CAR WASH    -> JOES CAR WASH  (processor: Square)
    SHELL OIL REFUND     -> SHELL OIL      (refund_marker: True)
    UBER*EATS            -> UBER *EATS     (the * is kept: it changes the meaning)

Rule: we never clean a key down to nothing. If a step would leave it empty,
we keep what we had.
"""

import re

from app.models import MerchantKey

# Card processors put their own name in front of the real shop's name.
PROCESSORS = {
    "SQ *": "Square",
    "TST *": "Toast",
    "PAYPAL *": "PayPal",
    "PP *": "PayPal",
    "PYPL *": "PayPal",
}

REFUND_WORDS = {"REFUND", "RETURN", "REVERSAL"}

US_STATES = set(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH "
    "NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
)


def merchant_key(description: str) -> MerchantKey:
    normalized = normalize(description)
    words = normalized.split(" ")

    processor = None
    for prefix, name in PROCESSORS.items():
        rest = normalized[len(prefix) :].strip()
        if normalized.startswith(prefix) and rest:
            processor = name
            words = rest.split(" ")
            break

    refund_marker = False
    without_refund_words = remove_refund_words(words)
    if without_refund_words and len(without_refund_words) < len(words):
        refund_marker = True
        words = without_refund_words

    # Drop trailing noise one word at a time: "SHELL OIL 57442 TX" -> "SHELL OIL".
    while len(words) > 1 and is_noise(words[-1]):
        words = words[:-1]

    return MerchantKey(
        key=" ".join(words),
        normalized=normalized,
        processor=processor,
        refund_marker=refund_marker,
    )


def normalize(description: str) -> str:
    """Upper-case, single spaces, and every `*` written as ` *`.

    So "uber*eats", "UBER* EATS" and "UBER *EATS" all become "UBER *EATS".
    """
    text = " ".join(description.upper().split())
    text = re.sub(r"\s*\*\s*", " *", text)
    return text.strip()


def remove_refund_words(words: list[str]) -> list[str]:
    """Drop REFUND / RETURN / REVERSAL anywhere, and CREDIT only as the last word.

    CREDIT is only a refund marker at the end: "AUTOZONE 123 CREDIT" is a refund,
    but "CREDIT CARD PAYMENT" is not.
    """
    kept = [word for word in words if word not in REFUND_WORDS]
    if len(kept) > 1 and kept[-1] == "CREDIT":
        kept = kept[:-1]
    return kept


def is_noise(word: str) -> bool:
    """A trailing word that says nothing about the merchant."""
    return (
        is_store_number(word) or is_reference_code(word) or is_short_date(word) or word in US_STATES
    )


def is_store_number(word: str) -> bool:
    """0091, #1402, 123-45"""
    digits = word.removeprefix("#").replace("-", "")
    return digits.isdigit()


def is_reference_code(word: str) -> bool:
    """Codes that mix letters and digits: *AB12CD, XXXX1234 (masked card number).

    Needs at least 5 characters and a digit, so words like "7UP" are left alone.
    """
    code = word.removeprefix("*")
    return len(code) >= 5 and code.isalnum() and any(ch.isdigit() for ch in code)


def is_short_date(word: str) -> bool:
    """01/18 or 01/18/2025"""
    parts = word.split("/")
    return len(parts) in (2, 3) and all(part.isdigit() for part in parts)
