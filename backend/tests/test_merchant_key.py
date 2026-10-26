import pytest

from app.brain.merchant_key import merchant_key


@pytest.mark.parametrize(
    ("description", "key"),
    [
        ("SHELL OIL 57442 TX", "SHELL OIL"),
        ("shell   oil 57442  tx", "SHELL OIL"),
        ("JOES CAFE 9921", "JOES CAFE"),
        ("JIFFY LUBE #1402", "JIFFY LUBE"),
        ("CHEVRON 0091", "CHEVRON"),
        ("AMAZON MKTPL*AB12CD3", "AMAZON MKTPL"),
        ("TRANSFER TO SAVINGS XXXX4410", "TRANSFER TO SAVINGS"),
        ("STARBUCKS 01/18", "STARBUCKS"),
        ("UBER *TRIP", "UBER *TRIP"),
        ("UBER*EATS", "UBER *EATS"),
        ("UBER* TRIP HELP.UBER.COM", "UBER *TRIP HELP.UBER.COM"),
    ],
)
def test_key_cleaning(description: str, key: str) -> None:
    assert merchant_key(description).key == key


@pytest.mark.parametrize(
    ("description", "key", "processor"),
    [
        ("SQ *JOES CAR WASH", "JOES CAR WASH", "Square"),
        ("TST* PIZZA PLACE 22", "PIZZA PLACE", "Toast"),
        ("PAYPAL *XYZ123", "XYZ123", "PayPal"),
        ("PP*ACME SUPPLY", "ACME SUPPLY", "PayPal"),
        ("PYPL *ACME", "ACME", "PayPal"),
    ],
)
def test_processor_prefix_is_stripped_and_recorded(description, key, processor) -> None:
    result = merchant_key(description)
    assert (result.key, result.processor) == (key, processor)


def test_refund_marker_keeps_the_purchase_key() -> None:
    result = merchant_key("SHELL OIL REFUND")
    assert result.key == "SHELL OIL"
    assert result.refund_marker


def test_credit_word_only_counts_as_refund_at_the_end() -> None:
    assert not merchant_key("CREDIT CARD PAYMENT NOVA CARD").refund_marker
    assert merchant_key("AUTOZONE 123 CREDIT").refund_marker


def test_never_strips_to_empty() -> None:
    assert merchant_key("12345").key == "12345"
    assert merchant_key("REFUND").key == "REFUND"
    assert merchant_key("SQ *").key == "SQ *"


def test_state_code_alone_is_kept() -> None:
    assert merchant_key("TX").key == "TX"
