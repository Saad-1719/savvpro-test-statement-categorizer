"""The decision policy (SDS 5.3).

Input: the evidence each layer found for one row.
Output: one Decision with status auto, review or excluded.

The steps run in order and the first one that applies wins.
The rule of thumb: if we are not sure, the row goes to review.
"""

from app.brain.layers import first_match
from app.models import Decision, Evidence, MerchantKey, Rule, Transaction
from app.rules.loader import RuleSet

# These categories are not income or spending, so they never count in totals.
EXCLUDED_CATEGORIES = {"Transfer", "Card Payment"}


def decide(
    tx: Transaction,
    key: MerchantKey,
    evidence_by_layer: dict[str, Evidence],
    rules: RuleSet,
) -> Decision:
    all_evidence = list(evidence_by_layer.values())

    # The three ways a row can end. They only fill in a Decision.
    def auto(category: str, reason: str, rule_id: str, refund_of: str | None = None) -> Decision:
        return Decision(
            transaction_id=tx.id,
            merchant_key=key.key,
            status="auto",
            category=category,
            reason=reason,
            rule_id=rule_id,
            evidence=all_evidence,
            refund_of=refund_of,
        )

    def excluded(category: str, reason: str, rule_id: str) -> Decision:
        return Decision(
            transaction_id=tx.id,
            merchant_key=key.key,
            status="excluded",
            category=category,
            reason=reason,
            rule_id=rule_id,
            evidence=all_evidence,
        )

    def review(reason: str, suggestion: str | None = None, rule_id: str | None = None) -> Decision:
        if suggestion:
            reason = f"{reason} (suggested: {suggestion})"
        return Decision(
            transaction_id=tx.id,
            merchant_key=key.key,
            status="review",
            category=None,
            suggestion=suggestion,
            reason=reason,
            rule_id=rule_id,
            evidence=all_evidence,
        )

    type_match = evidence_by_layer.get("type")
    user_match = evidence_by_layer.get("user")
    merchant_match = evidence_by_layer.get("merchant")

    # Step 1. Transfers and card payments are excluded. Bank fees are auto.
    if type_match:
        if type_match.category in EXCLUDED_CATEGORIES:
            return excluded(type_match.category, type_match.reason, type_match.rule_id)
        return auto(type_match.category, type_match.reason, type_match.rule_id)

    # Step 2. The user saved an "always" rule for this merchant.
    if user_match:
        return auto(user_match.category, user_match.reason, user_match.rule_id)

    # Step 3. Money coming back from a shop we know as an expense is a refund, not income.
    if tx.is_credit:
        refund_rule = find_refund_rule(tx, key, rules)
        if refund_rule:
            reason = f"Money back from {refund_rule.pattern}, reduces {refund_rule.category}"
            return auto("Refund", reason, refund_rule.id, refund_of=refund_rule.category)
        if key.refund_marker:
            return review("Refund from an unknown merchant")

    # Step 4. Stores like Walmart sell both business and personal things.
    deny_name = find_deny_list_name(key, rules)
    if deny_name:
        return review(
            f"Ambiguous merchant ({deny_name}); could be business or personal",
            rule_id=f"deny.{deny_name.lower()}",
        )

    merchant_rule = rules.by_id[merchant_match.rule_id] if merchant_match else None

    # Step 5. A "review" rule: we know this merchant, and we know we cannot tell.
    if merchant_rule and merchant_rule.action == "review":
        return review(merchant_rule.reason, rule_id=merchant_rule.id)

    # Step 6. Too large for the rule, e.g. $142 at a gas station may include store items.
    if merchant_rule and is_over_limit(tx, merchant_rule):
        return review(
            f"Amount above {merchant_rule.category.lower()} limit of "
            f"${merchant_rule.max_amount}; may include store items",
            suggestion=merchant_rule.category,
            rule_id=merchant_rule.id,
        )

    # What do the layers say? Weak evidence never counts as a claim.
    with_category = [e for e in all_evidence if e.category]
    claimed_categories = {e.category for e in with_category if e.strength != "weak"}
    strong = [e for e in with_category if e.strength == "strong"]

    # Step 7. At least one strong rule, and every layer agrees.
    if strong and len(claimed_categories) == 1:
        winner = strong[0]
        return auto(winner.category, winner.reason, winner.rule_id)

    # Step 8. Two layers name different categories.
    if len(claimed_categories) > 1:
        reasons = "; ".join(e.reason for e in with_category)
        return review(f"Conflicting rules: {reasons}")

    # Step 9. Only medium or weak evidence: suggest, but let the user decide.
    if with_category:
        hint = with_category[0]
        return review("Weak match only", suggestion=hint.category, rule_id=hint.rule_id)

    # Step 10. No rule matched at all.
    if key.processor:
        return review(f"{key.processor} payment, merchant unknown")
    if tx.is_credit:
        return review("Money in from an unknown source; not assumed to be income")
    return review("Unknown merchant")


def find_refund_rule(tx: Transaction, key: MerchantKey, rules: RuleSet) -> Rule | None:
    """Find the expense rule this credit is money back from, if any.

    Example: SHELL OIL +20.00 matches the Shell rule (a debit rule), so it is a Fuel refund.
    """
    expense_merchant_rules = [
        rule for rule in rules.merchants if rule.sign == "debit" and rule.action == "categorize"
    ]
    rule = first_match(expense_merchant_rules, key.key, tx, ignore_sign=True)
    if rule:
        return rule

    # With the word REFUND in the description, a keyword is enough (e.g. "CAR WASH REFUND").
    if key.refund_marker:
        return first_match(rules.keywords, key.key, tx, ignore_sign=True)
    return None


def find_deny_list_name(key: MerchantKey, rules: RuleSet) -> str | None:
    """Return the deny-listed name the merchant key starts with, e.g. WALMART."""
    for name in rules.deny_list:
        if key.key == name or key.key.startswith(name + " "):
            return name
    return None


def is_over_limit(tx: Transaction, rule: Rule) -> bool:
    if rule.max_amount is None:
        return False
    return abs(tx.amount) > rule.max_amount
