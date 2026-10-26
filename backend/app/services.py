"""The actions the API offers: upload, change rows, save an "always" rule.

State lives in store.py. Changes to one session's decisions hold that session's lock.
"""

import logging
import re
import uuid
from collections import Counter

from app.brain.engine import categorize_one
from app.config import settings
from app.errors import ServiceError
from app.ingest.parser import parse_statement
from app.models import Decision, FileSummary, Transaction, UserRule
from app.rules.loader import RuleSet, default_rules
from app.store import Session, SessionStore, UserRuleStore

logger = logging.getLogger(__name__)

sessions = SessionStore(
    ttl_seconds=settings.session_ttl_minutes * 60,
    max_sessions=settings.max_sessions,
)
user_rules = UserRuleStore()


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

    saved_rules = user_rules.all()
    session = Session(
        id=uuid.uuid4().hex,
        tax_year=year,
        transactions=transactions,
        decisions={tx.id: categorize_one(tx, rules, saved_rules) for tx in transactions},
        file_summaries=summaries,
    )
    sessions.add(session)

    # Counts only: never log descriptions or amounts (they are personal financial data).
    statuses = Counter(d.status for d in session.decisions.values())
    logger.info(
        "session %s: %d file(s), %d rows (%d auto, %d review, %d excluded)",
        session.id[:8],
        len(files),
        len(transactions),
        statuses["auto"],
        statuses["review"],
        statuses["excluded"],
    )
    return session


def update_transaction(
    session: Session,
    tx_id: str,
    category: str | None,
    business_pct: int | None,
    rules: RuleSet | None = None,
) -> Decision:
    """Change one row. Same rules as `update_transactions`."""
    return update_transactions(session, [tx_id], category, business_pct, rules)[0]


def update_transactions(
    session: Session,
    tx_ids: list[str],
    category: str | None,
    business_pct: int | None,
    rules: RuleSet | None = None,
) -> list[Decision]:
    """Change several rows at once: all of them, or none if any row fails a check."""
    rules = rules or default_rules()
    if not tx_ids:
        raise ServiceError("invalid_request", "Choose at least one transaction.")
    if category is None and business_pct is None:
        raise ServiceError("invalid_request", "Send a category, a business_pct, or both.")

    with session.lock:
        missing = [tx_id for tx_id in tx_ids if tx_id not in session.by_id]
        if missing:
            raise ServiceError(
                "transaction_not_found", "Transaction not found.", 404, {"missing": missing}
            )

        # First work out every new decision. Nothing is saved until all of them pass.
        new_decisions = [
            changed_decision(session, tx_id, category, business_pct, rules) for tx_id in tx_ids
        ]
        for tx_id, decision in zip(tx_ids, new_decisions, strict=True):
            session.decisions[tx_id] = decision

    logger.info("session %s: user changed %d row(s)", session.id[:8], len(tx_ids))
    return new_decisions


def changed_decision(
    session: Session,
    tx_id: str,
    category: str | None,
    business_pct: int | None,
    rules: RuleSet,
) -> Decision:
    """Return the row's decision with the user's change applied. Raises if not allowed.

    The category is applied first, so a business % is checked against the new category.
    """
    decision = session.decisions[tx_id].model_copy(deep=True)

    if category is not None:
        check_category(category, rules)
        if "outside_tax_year" in session.by_id[tx_id].flags:
            raise ServiceError(
                "outside_tax_year",
                f"This row is not in tax year {session.tax_year}, so it cannot be counted.",
            )
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

    return decision


def add_user_rule(
    session: Session,
    merchant_key: str,
    category: str,
    apply_to_existing: bool = True,
    rules: RuleSet | None = None,
) -> tuple[UserRule, int]:
    """Save "always MERCHANT as CATEGORY" and re-decide that merchant's rows in this session.

    Rows the user changed by hand are left alone.
    """
    rules = rules or default_rules()
    check_category(category, rules)
    key = " ".join(merchant_key.upper().split())
    if not key:
        raise ServiceError("invalid_merchant_key", "Merchant key is empty.")

    rule = UserRule(id=f"user.{slug(key)}", merchant_key=key, category=category)
    user_rules.save(rule)

    updated = 0
    if apply_to_existing:
        saved_rules = user_rules.all()
        with session.lock:
            for tx in session.transactions:
                old = session.decisions[tx.id]
                if old.merchant_key != key or old.rule_id == "user.manual":
                    continue
                new = categorize_one(tx, rules, saved_rules)
                if new.category == old.category:
                    new.business_pct = old.business_pct
                if (new.status, new.category) != (old.status, old.category):
                    updated += 1
                session.decisions[tx.id] = new

    logger.info("session %s: saved rule %s, %d row(s) updated", session.id[:8], rule.id, updated)
    return rule, updated


def check_category(category: str, rules: RuleSet) -> None:
    if category not in rules.categories:
        raise ServiceError(
            "invalid_category",
            f"Unknown category {category!r}.",
            details={"categories": list(rules.categories)},
        )


def slug(text: str) -> str:
    """'JOES CAFE' -> 'joes_cafe'"""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
