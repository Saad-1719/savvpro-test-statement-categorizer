"""Session state and the use cases the API exposes.

State is in memory behind a small store so a database can replace it later.
User rules are kept app-wide so an "always" rule also applies to future uploads.
"""

import re
import threading
import uuid
from dataclasses import dataclass, field

from app.brain.engine import categorize_one
from app.ingest.parser import parse_statement
from app.models import Decision, FileSummary, Transaction, UserRule
from app.rules.loader import RuleSet, default_rules


class ServiceError(Exception):
    def __init__(self, code: str, message: str, status: int = 422, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}


@dataclass
class Session:
    id: str
    tax_year: int
    transactions: list[Transaction]
    decisions: dict[str, Decision]
    file_summaries: list[FileSummary]
    by_id: dict[str, Transaction] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.by_id = {tx.id: tx for tx in self.transactions}


class Store:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self.user_rules: list[UserRule] = []
        self.lock = threading.RLock()

    def add(self, session: Session) -> None:
        with self.lock:
            self._sessions[session.id] = session

    def get(self, session_id: str) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise ServiceError("session_not_found", "Session not found; upload again.", 404)
        return session


store = Store()


def _decide(tx: Transaction, rules: RuleSet) -> Decision:
    return categorize_one(tx, rules, store.user_rules)


def create_session(
    files: list[tuple[str, bytes]], tax_year: int | None, rules: RuleSet | None = None
) -> Session:
    rules = rules or default_rules()
    transactions: list[Transaction] = []
    summaries: list[FileSummary] = []
    year = tax_year
    for name, data in files:
        txs, summary, year = parse_statement(name, data, year)
        transactions.extend(txs)
        summaries.append(summary)
    session = Session(
        id=uuid.uuid4().hex,
        tax_year=year,
        transactions=transactions,
        decisions={tx.id: _decide(tx, rules) for tx in transactions},
        file_summaries=summaries,
    )
    store.add(session)
    return session


def _check_category(category: str, rules: RuleSet) -> None:
    if category not in rules.categories:
        raise ServiceError(
            "invalid_category",
            f"Unknown category {category!r}.",
            details={"categories": list(rules.categories)},
        )


def update_transaction(
    session: Session,
    tx_id: str,
    category: str | None,
    business_pct: int | None,
    rules: RuleSet | None = None,
) -> Decision:
    rules = rules or default_rules()
    if tx_id not in session.by_id:
        raise ServiceError("transaction_not_found", "Transaction not found.", 404)
    decision = session.decisions[tx_id].model_copy(deep=True)

    if category is not None:
        _check_category(category, rules)
        kind = rules.categories[category].kind
        decision.status = "excluded" if kind == "excluded" else "auto"
        if category != "Refund":
            decision.refund_of = None
        decision.category = category
        decision.reason = f"Set by you: {category}"
        decision.rule_id = "user.manual"
        decision.decided_by = "user"

    if business_pct is not None:
        if not decision.category or not rules.categories[decision.category].mixed_use:
            raise ServiceError(
                "business_pct_not_allowed",
                "A business-use % only applies to mixed-use categories such as Phone & Data.",
            )
        if not 0 <= business_pct <= 100:
            raise ServiceError("invalid_business_pct", "Business-use % must be 0 to 100.")
        decision.business_pct = business_pct

    session.decisions[tx_id] = decision
    return decision


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def add_user_rule(
    session: Session,
    merchant_key: str,
    category: str,
    apply_to_existing: bool = True,
    rules: RuleSet | None = None,
) -> tuple[UserRule, int]:
    rules = rules or default_rules()
    _check_category(category, rules)
    key = " ".join(merchant_key.upper().split())
    if not key:
        raise ServiceError("invalid_merchant_key", "Merchant key is empty.")
    rule = UserRule(id=f"user.{_slug(key)}", merchant_key=key, category=category)
    with store.lock:
        store.user_rules = [r for r in store.user_rules if r.merchant_key != key] + [rule]

    updated = 0
    if apply_to_existing:
        for tx in session.transactions:
            old = session.decisions[tx.id]
            if old.merchant_key != key or old.rule_id == "user.manual":
                continue
            new = _decide(tx, rules)
            new.business_pct = old.business_pct if new.category == old.category else None
            if (new.status, new.category) != (old.status, old.category):
                updated += 1
            session.decisions[tx.id] = new
    return rule, updated
