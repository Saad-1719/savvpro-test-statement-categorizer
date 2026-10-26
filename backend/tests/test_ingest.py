from datetime import date
from decimal import Decimal

import pytest

from app.ingest.amounts import parse_amount, parse_date
from app.ingest.parser import IngestError, parse_statement
from tests.conftest import SAMPLE_DIR

HEADER = "Date,Description,Amount,Balance\n"


def parse(text: str, tax_year: int | None = None):
    return parse_statement("t.csv", text.encode(), tax_year)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("-18.40", "-18.40"),
        ("18.40", "18.40"),
        ("+18.40", "18.40"),
        ("(25.00)", "-25.00"),
        ("15.00-", "-15.00"),
        ("$1,234.50", "1234.50"),
        ("-$850.00", "-850.00"),
        ("$-850.00", "-850.00"),
        (" 7 ", "7"),
    ],
)
def test_amount_formats(text: str, expected: str) -> None:
    assert parse_amount(text) == Decimal(expected)


@pytest.mark.parametrize("text", ["", "abc", "1.2.3", "12.345", "--5", "$"])
def test_bad_amounts_raise(text: str) -> None:
    with pytest.raises(ValueError):
        parse_amount(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [("01/18/2025", date(2025, 1, 18)), ("2025-01-18", date(2025, 1, 18)),
     ("18 Jan 2025", date(2025, 1, 18))],
)  # fmt: skip
def test_date_formats(text: str, expected: date) -> None:
    assert parse_date(text) == expected


def test_bad_date_raises() -> None:
    with pytest.raises(ValueError):
        parse_date("18.01.2025")


def test_signed_layout() -> None:
    txs, summary, year = parse(HEADER + "01/03/2025,UBER PAYOUT,412.30,1\n01/04/2025,SHELL,-4,1\n")
    assert summary.layout == "first_federal_checking"
    assert [tx.amount for tx in txs] == [Decimal("412.30"), Decimal("-4")]
    assert summary.money_in == Decimal("412.30")
    assert summary.money_out == Decimal("-4")
    assert year == 2025


def test_header_is_case_and_space_insensitive() -> None:
    txs, _, _ = parse(" date , DESCRIPTION,Amount ,balance\n01/03/2025,X,1,1\n")
    assert len(txs) == 1


def test_unknown_layout_is_rejected_with_supported_list() -> None:
    with pytest.raises(IngestError) as err:
        parse("When,What,How Much\n01/03/2025,X,1\n")
    assert err.value.code == "unrecognized_layout"
    assert "first_federal_checking" in err.value.message


def test_header_must_be_in_first_15_lines() -> None:
    with pytest.raises(IngestError):
        parse("junk\n" * 15 + HEADER + "01/03/2025,X,1,1\n")


def test_header_with_no_rows_is_rejected() -> None:
    with pytest.raises(IngestError) as err:
        parse(HEADER)
    assert err.value.code == "no_transactions"


def test_too_many_bad_rows_rejects_the_file() -> None:
    rows = "".join(f"bad-date,X{i},1,1\n" for i in range(3)) + "01/03/2025,OK,1,1\n" * 5
    with pytest.raises(IngestError) as err:
        parse(HEADER + rows)
    assert err.value.code == "too_many_bad_rows"


def test_a_few_bad_rows_are_skipped_and_reported() -> None:
    rows = "bad-date,X,1,1\n" + "".join(f"01/03/2025,OK {i},1,1\n" for i in range(12))
    txs, summary, _ = parse(HEADER + rows)
    assert len(txs) == 12
    assert summary.rows_skipped[0].row_number == 2
    assert "Bad date" in summary.rows_skipped[0].reason


def test_latin1_and_semicolon_files() -> None:
    data = "Date;Description;Amount;Balance\n01/03/2025;CAF\xc9 PARIS;-3,00;1\n"
    txs, _, _ = parse_statement("t.csv", data.encode("latin-1"))
    assert txs[0].raw_description == "CAF\xc9 PARIS"


def test_ids_are_stable() -> None:
    first, _, _ = parse(HEADER + "01/03/2025,X,1,1\n")
    second, _, _ = parse(HEADER + "01/03/2025,X,1,1\n")
    assert first[0].id == second[0].id


def test_sample_file_parses_cleanly() -> None:
    data = (SAMPLE_DIR / "first_federal_checking_2025.csv").read_bytes()
    txs, summary, year = parse_statement("sample.csv", data)
    assert year == 2025
    assert summary.rows_skipped == []
    assert summary.rows_read == len(txs) > 0


def test_shop_named_total_is_not_a_footer() -> None:
    txs, summary, _ = parse(HEADER + "01/03/2025,TOTAL WINE & MORE,-20.00,1\n01/04/2025,X,-1,1\n")
    assert len(txs) == 2
    assert summary.footer_rows == 0


def test_date_order_comes_from_the_layout() -> None:
    """01/02/2025 is 2 January for a US bank and 1 February for a day-first bank."""
    assert parse_date("01/02/2025") == date(2025, 1, 2)
    assert parse_date("01/02/2025", ("%d/%m/%Y",)) == date(2025, 2, 1)


def test_every_layout_uses_one_day_month_order() -> None:
    from app.ingest.layouts import LAYOUTS

    for layout in LAYOUTS:
        month_first = "%m/%d/%Y" in layout.date_formats
        day_first = "%d/%m/%Y" in layout.date_formats
        assert not (month_first and day_first), layout.name
