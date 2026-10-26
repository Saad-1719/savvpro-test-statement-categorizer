"""Sessions expire and are capped; user rules replace each other per merchant."""

import pytest

from app.errors import ServiceError
from app.models import UserRule
from app.store import Session, SessionStore, UserRuleStore


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def new_session(session_id: str) -> Session:
    return Session(id=session_id, tax_year=2025, transactions=[], decisions={}, file_summaries=[])


def test_idle_session_expires() -> None:
    clock = FakeClock()
    store = SessionStore(ttl_seconds=60, max_sessions=10, clock=clock)
    store.add(new_session("a"))

    clock.now = 59
    assert store.get("a").id == "a"  # using it resets the idle timer

    clock.now = 59 + 61
    with pytest.raises(ServiceError) as err:
        store.get("a")
    assert err.value.code == "session_not_found"


def test_least_recently_used_session_is_dropped_at_the_limit() -> None:
    clock = FakeClock()
    store = SessionStore(ttl_seconds=1000, max_sessions=2, clock=clock)
    store.add(new_session("a"))
    clock.now = 1
    store.add(new_session("b"))
    clock.now = 2
    store.get("a")  # "a" is now more recently used than "b"
    clock.now = 3
    store.add(new_session("c"))

    assert len(store) == 2
    assert store.get("a") and store.get("c")
    with pytest.raises(ServiceError):
        store.get("b")


def test_saving_a_rule_replaces_the_old_rule_for_that_merchant() -> None:
    rules = UserRuleStore()
    rules.save(UserRule(id="user.joes_cafe", merchant_key="JOES CAFE", category="Supplies"))
    rules.save(UserRule(id="user.joes_cafe", merchant_key="JOES CAFE", category="Personal"))
    assert [r.category for r in rules.all()] == ["Personal"]


def test_all_returns_a_copy() -> None:
    rules = UserRuleStore()
    snapshot = rules.all()
    rules.save(UserRule(id="user.x", merchant_key="X", category="Personal"))
    assert snapshot == []
