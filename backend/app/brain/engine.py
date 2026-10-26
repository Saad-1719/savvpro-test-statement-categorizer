"""The brain's entry point: categorize(transactions) -> one Decision per row.

For each row:
  1. clean the description into a merchant key   (merchant_key.py)
  2. ask each layer for evidence                  (layers.py)
  3. apply the decision policy                    (decide.py)

No I/O, no randomness, no network: the same input always gives the same output.
"""

from app.brain.decide import decide
from app.brain.layers import keyword_evidence, merchant_evidence, type_evidence, user_evidence
from app.brain.merchant_key import merchant_key
from app.models import Decision, Transaction, UserRule
from app.rules.loader import RuleSet, default_rules


def categorize(
    transactions: list[Transaction],
    rules: RuleSet | None = None,
    user_rules: list[UserRule] | None = None,
) -> list[Decision]:
    rules = rules or default_rules()
    user_rules = user_rules or []
    return [categorize_one(tx, rules, user_rules) for tx in transactions]


def categorize_one(tx: Transaction, rules: RuleSet, user_rules: list[UserRule]) -> Decision:
    key = merchant_key(tx.raw_description)

    # Rows flagged while reading the file are not counted at all.
    if "duplicate" in tx.flags:
        return flagged(
            tx,
            key.key,
            "duplicate",
            "Same date, description and amount as an earlier row; counted once. "
            "Pick a category if it was a real second purchase.",
        )
    if "outside_tax_year" in tx.flags:
        return flagged(tx, key.key, "outside_tax_year", "Date is outside the tax year; not counted")

    # Ask every layer. A layer with nothing to say is left out.
    evidence_by_layer = {}
    type_ev = type_evidence(tx, key, rules.types)
    if type_ev:
        evidence_by_layer["type"] = type_ev
    user_ev = user_evidence(key, user_rules)
    if user_ev:
        evidence_by_layer["user"] = user_ev
    merchant_ev = merchant_evidence(tx, key, rules.merchants)
    if merchant_ev:
        evidence_by_layer["merchant"] = merchant_ev
    keyword_ev = keyword_evidence(tx, key, rules.keywords)
    if keyword_ev:
        evidence_by_layer["keyword"] = keyword_ev

    decision = decide(tx, key, evidence_by_layer, rules)

    # Decided by the user's own rule? Show it as the user's decision.
    if user_ev and decision.rule_id == user_ev.rule_id:
        decision.decided_by = "user"

    # Phone & Data is mixed use: it only counts once the user gives a business %.
    if decision.category and rules.categories[decision.category].mixed_use:
        decision.reason += "; set a business-use % before it counts"

    return decision


def flagged(tx: Transaction, key: str, flag: str, reason: str) -> Decision:
    return Decision(
        transaction_id=tx.id,
        merchant_key=key,
        status="excluded",
        category=None,
        reason=reason,
        rule_id=f"flag.{flag}",
    )
