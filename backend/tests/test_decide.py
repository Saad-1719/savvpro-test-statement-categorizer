"""One test per line of the decision policy (SDS 5.3)."""

from app.models import UserRule
from tests.conftest import run


def test_1_type_rule_excludes_transfers() -> None:
    d = run("ONLINE TRANSFER TO CHECKING", "-100.00")
    assert (d.status, d.category, d.rule_id) == (
        "excluded",
        "Transfer",
        "type.transfer_own_account",
    )


def test_1_type_rule_makes_bank_fees_auto() -> None:
    d = run("ATM FEE", "-3.00")
    assert (d.status, d.category) == ("auto", "Bank Fees")


def test_1_type_rule_beats_user_rule() -> None:
    rule = UserRule(id="user.x", merchant_key="TRANSFER TO SAVINGS", category="Personal")
    assert run("TRANSFER TO SAVINGS", "-5.00", [rule]).category == "Transfer"


def test_2_user_rule_beats_deny_list() -> None:
    rule = UserRule(id="user.walmart", merchant_key="WALMART SUPERCENTER", category="Supplies")
    d = run("WALMART SUPERCENTER #2231", "-63.20", [rule])
    assert (d.status, d.category, d.decided_by) == ("auto", "Supplies", "user")


def test_3_credit_from_expense_merchant_is_refund() -> None:
    d = run("AUTOZONE 123", "15.00")
    assert (d.status, d.category, d.refund_of) == ("auto", "Refund", "Vehicle Maintenance")


def test_3_refund_from_unknown_merchant_goes_to_review() -> None:
    d = run("RANDOM SHOP REFUND", "15.00")
    assert d.status == "review"
    assert "Refund from an unknown merchant" in d.reason


def test_4_deny_list() -> None:
    d = run("TARGET 00012", "-30.00")
    assert d.status == "review"
    assert "Ambiguous merchant" in d.reason


def test_5_review_rule_uses_its_reason() -> None:
    d = run("UBER BV", "-9.99")
    assert d.status == "review"
    assert d.reason == "Uber charge with no ride or eats marker"
    assert d.rule_id == "merchant.uber_ambiguous"


def test_6_amount_limit_compares_absolute_amount() -> None:
    assert run("SHELL OIL", "-99.99").status == "auto"
    assert run("SHELL OIL", "-100.00").status == "auto"
    d = run("SHELL OIL", "-100.01")
    assert (d.status, d.suggestion) == ("review", "Fuel")


def test_7_strong_agreeing_evidence_is_auto() -> None:
    d = run("JIFFY LUBE OIL CHANGE", "-50.00")  # merchant and keyword agree
    assert (d.status, d.category) == ("auto", "Vehicle Maintenance")


def test_8_conflict_goes_to_review_with_both_reasons() -> None:
    d = run("KROGER FUEL 22", "-40.00")
    assert d.status == "review"
    assert "KROGER" in d.reason and "FUEL" in d.reason


def test_9_medium_only_is_a_suggestion_not_a_decision() -> None:
    d = run("BOBS TIRE SHOP", "-80.00")
    assert (d.status, d.category, d.suggestion) == ("review", None, "Vehicle Maintenance")


def test_10_unknown_debit() -> None:
    d = run("JOES CAFE 9921", "-8.75")
    assert (d.status, d.suggestion, d.reason) == ("review", None, "Unknown merchant")


def test_10_unknown_credit_is_not_income() -> None:
    d = run("VENMO CASHOUT", "150.00")
    assert d.status == "review"
    assert "not assumed to be income" in d.reason


def test_10_unknown_processor_merchant() -> None:
    d = run("SQ *MYSTERY 77", "-5.00")
    assert d.reason == "Square payment, merchant unknown"


def test_prefix_needs_word_boundary() -> None:
    assert run("SHELLYS BAKERY", "-5.00").status == "review"


def test_every_decision_has_reason() -> None:
    for desc, amount in [("SHELL", "-1"), ("ZZZ", "-1"), ("ZZZ", "1"), ("AUTOPAY", "50")]:
        assert run(desc, amount).reason


def test_deterministic() -> None:
    assert run("CHEVRON 0091", "-142.00") == run("CHEVRON 0091", "-142.00")
