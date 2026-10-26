"""The 20 messy cases from SRS section 5, one test each."""

from datetime import date
from decimal import Decimal

import pytest

from app.ingest.parser import parse_statement
from app.models import UserRule
from app.reports.totals import build_summary
from app.rules.loader import default_rules
from app.services import ServiceError, add_user_rule, create_session, update_transaction
from tests.conftest import run

HEADER = "Date,Description,Amount,Balance\n"


@pytest.mark.parametrize(
    ("case", "description", "amount", "status", "category"),
    [
        ("E1 payout", "UBER TECHNOLOGIES PAYOUT", "412.30", "auto", "Platform Income"),
        ("E1 trip", "UBER *TRIP", "-18.40", "auto", "Personal"),
        ("E2", "UBER *EATS", "-24.10", "auto", "Personal"),
        ("E3", "UBER BV", "-9.99", "review", None),
        ("E5", "TRANSFER TO SAVINGS", "-500.00", "excluded", "Transfer"),
        ("E6", "PAYMENT THANK YOU", "850.00", "excluded", "Card Payment"),
        ("E7", "CHEVRON 0091", "-142.00", "review", None),
        ("E8", "VERIZON WRLS", "-85.00", "auto", "Phone & Data"),
        ("E9", "SQ *JOES CAR WASH", "-15.00", "auto", "Vehicle Maintenance"),
        ("E10", "PAYPAL *XYZ123", "-40.00", "review", None),
        ("E11", "WALMART SUPERCENTER", "-63.20", "review", None),
        ("E12", "JOES CAFE 9921", "-8.75", "review", None),
        ("E13", "SAFEWAY FUEL 1187", "-56.40", "review", None),
        ("E14", "FOREIGN TRANSACTION FEE", "-1.20", "auto", "Bank Fees"),
        ("E19", "DOORDASH FEE", "-2.00", "auto", "Platform Fees"),
    ],
)
def test_single_row_cases(case, description, amount, status, category) -> None:
    d = run(description, amount)
    assert (d.status, d.category) == (status, category), f"{case}: {d.reason}"


def test_e3_reason() -> None:
    assert run("UBER BV", "-9.99").reason == "Uber charge with no ride or eats marker"


def test_e4_refund_reduces_fuel_and_is_not_income() -> None:
    d = run("SHELL OIL REFUND", "20.00")
    assert (d.status, d.category, d.refund_of) == ("auto", "Refund", "Fuel")

    session = create_session(
        [("r.csv", (HEADER + "01/04/2025,SHELL OIL 1,-50.00,1\n"
                    "01/05/2025,SHELL OIL REFUND,20.00,1\n").encode())],
        None,
    )  # fmt: skip
    summary = build_summary(session.transactions, session.decisions, default_rules().categories)
    fuel = next(t for t in summary["totals"] if t["category"] == "Fuel")
    assert fuel["deductible_amount"] == Decimal("30.00")
    assert summary["income_total"] == 0


def test_e7_suggests_fuel_and_says_why() -> None:
    d = run("CHEVRON 0091", "-142.00")
    assert d.suggestion == "Fuel"
    assert "store items" in d.reason


def test_e8_phone_needs_business_pct_before_it_counts() -> None:
    session = create_session(
        [("p.csv", (HEADER + "01/14/2025,VERIZON WRLS,-85.00,1\n").encode())], None
    )
    categories = default_rules().categories
    summary = build_summary(session.transactions, session.decisions, categories)
    assert summary["phone_missing_pct_count"] == 1
    assert not summary["is_final"]

    tx = session.transactions[0]
    session.decisions[tx.id].business_pct = 60
    summary = build_summary(session.transactions, session.decisions, categories)
    phone = next(t for t in summary["totals"] if t["category"] == "Phone & Data")
    assert phone["deductible_amount"] == Decimal("51.00")
    assert summary["is_final"]


def test_e10_reason() -> None:
    assert run("PAYPAL *XYZ123", "-40.00").reason == "PayPal payment, merchant unknown"


def test_e11_deny_list_yields_to_user_rule() -> None:
    rule = UserRule(id="user.w", merchant_key="WALMART SUPERCENTER", category="Personal")
    assert run("WALMART SUPERCENTER #2231", "-63.20", [rule]).status == "auto"


def test_e12_no_guess() -> None:
    d = run("JOES CAFE 9921", "-8.75")
    assert d.suggestion is None and d.category is None


def test_e13_shows_both_reasons() -> None:
    d = run("SAFEWAY FUEL 1187", "-56.40")
    assert "Conflicting rules" in d.reason
    assert "SAFEWAY" in d.reason and "FUEL" in d.reason


def test_e15_duplicate_is_flagged_and_counted_once() -> None:
    row = "01/18/2025,JOES CAFE 9921,-8.75,1\n"
    session = create_session([("d.csv", (HEADER + row + row).encode())], None)
    assert session.file_summaries[0].duplicates == 1
    first, second = (session.decisions[t.id] for t in session.transactions)
    assert first.status == "review"
    assert (second.status, second.rule_id) == ("excluded", "flag.duplicate")
    summary = build_summary(session.transactions, session.decisions, default_rules().categories)
    assert summary["unreviewed_amount"] == Decimal("8.75")


def test_e16_debit_credit_columns_are_signed() -> None:
    text = (
        "Posting Date,Details,Debit,Credit\n"
        "01/03/2025,UBER TECHNOLOGIES PAYOUT,,412.30\n"
        "01/04/2025,SHELL OIL 57442,42.10,\n"
    )
    txs, summary, _ = parse_statement("m.csv", text.encode())
    assert summary.layout == "metro_bank_checking"
    assert [tx.amount for tx in txs] == [Decimal("412.30"), Decimal("-42.10")]


def test_e17_junk_header_and_footer_are_skipped_and_reported() -> None:
    text = (
        "First Federal Bank\nAccount Number: XXXX4410\n\n"
        + HEADER
        + "01/03/2025,UBER PAYOUT,412.30,1\n\n"
        + "Ending Balance,,,3205.34\nTotal Transactions,,,1\n"
    )
    txs, summary, _ = parse_statement("j.csv", text.encode())
    assert len(txs) == 1
    assert summary.junk_rows_before_header == 2
    assert summary.footer_rows == 2


def test_e17_footer_without_blank_line() -> None:
    txs, summary, _ = parse_statement("j.csv", (HEADER + "01/03/2025,X,1,1\nTotal,,,1\n").encode())
    assert len(txs) == 1 and summary.footer_rows == 1


def test_e18_row_outside_tax_year_is_flagged_and_excluded() -> None:
    text = (
        HEADER
        + "12/28/2024,SHELL OIL,-42.10,1\n01/04/2025,SHELL OIL,-48.15,1\n01/05/2025,SHELL,-1,1\n"
    )
    session = create_session([("y.csv", text.encode())], None)
    assert session.tax_year == 2025
    assert session.file_summaries[0].outside_tax_year == 1
    old = next(t for t in session.transactions if t.date == date(2024, 12, 28))
    assert session.decisions[old.id].rule_id == "flag.outside_tax_year"
    summary = build_summary(session.transactions, session.decisions, default_rules().categories)
    fuel = next(t for t in summary["totals"] if t["category"] == "Fuel")
    assert fuel["deductible_amount"] == Decimal("49.15")


def test_e20_always_rule_updates_now_and_future_uploads() -> None:
    text = HEADER + "01/18/2025,JOES CAFE 9921,-8.75,1\n02/14/2025,JOES CAFE 9921,-12.25,1\n"
    session = create_session([("a.csv", text.encode())], None)
    assert all(d.status == "review" for d in session.decisions.values())

    rule, updated = add_user_rule(session, "JOES CAFE", "Personal")
    assert updated == 2
    assert all(
        (d.status, d.category, d.decided_by) == ("auto", "Personal", "user")
        for d in session.decisions.values()
    )

    later = create_session(
        [("b.csv", (HEADER + "03/01/2025,JOES CAFE 1,-4.00,1\n").encode())], None
    )
    (decision,) = later.decisions.values()
    assert (decision.category, decision.rule_id) == ("Personal", rule.id)


def test_e4_refund_shows_its_evidence() -> None:
    d = run("SHELL OIL REFUND", "20.00")
    assert [(e.rule_id, e.category) for e in d.evidence] == [("merchant.shell", "Fuel")]


def test_e15_a_kept_duplicate_counts() -> None:
    """The user says the second coffee was real: it is counted after all."""
    row = "01/18/2025,JOES CAFE 9921,-8.75,1\n"
    session = create_session([("d.csv", (HEADER + row + row).encode())], None)
    duplicate = next(t for t in session.transactions if "duplicate" in t.flags)
    update_transaction(session, duplicate.id, "Personal", None)
    assert session.decisions[duplicate.id].status == "auto"


def test_e18_row_outside_tax_year_cannot_be_counted() -> None:
    text = HEADER + "12/28/2024,SHELL OIL,-42.10,1\n01/04/2025,SHELL OIL,-48.15,1\n"
    session = create_session([("y.csv", text.encode())], None)
    old = next(t for t in session.transactions if t.date.year == 2024)
    with pytest.raises(ServiceError) as err:
        update_transaction(session, old.id, "Fuel", None)
    assert err.value.code == "outside_tax_year"
