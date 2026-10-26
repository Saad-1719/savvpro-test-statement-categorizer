import hashlib
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.brain.engine import categorize_one
from app.models import Decision, Transaction, UserRule
from app.rules.loader import default_rules
from app.services import store

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample_data"


@pytest.fixture(autouse=True)
def _clean_user_rules():
    """User rules are app-wide state; keep tests independent."""
    store.user_rules = []
    yield
    store.user_rules = []


def make_tx(
    description: str,
    amount: str,
    *,
    on: date = date(2025, 3, 1),
    account: str = "checking",
    flags: list[str] | None = None,
) -> Transaction:
    return Transaction(
        id=hashlib.sha1(f"{description}{amount}{on}".encode()).hexdigest()[:12],
        source_file="test.csv",
        row_number=1,
        date=on,
        raw_description=description,
        amount=Decimal(amount),
        account=account,
        flags=flags or [],
    )


def run(description: str, amount: str, user_rules: list[UserRule] | None = None) -> Decision:
    return categorize_one(make_tx(description, amount), default_rules(), user_rules or [])
