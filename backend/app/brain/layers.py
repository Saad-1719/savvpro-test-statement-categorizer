"""The evidence layers: type, user, merchant and keyword.

Each layer looks through its own rule list and returns at most one piece of
evidence: the first rule that matches. The loader has already sorted every list
so the most specific rule comes first (e.g. "UBER *EATS" before "UBER").

Layers never decide anything. decide.py does that.
"""

import re

from app.models import Evidence, MerchantKey, Rule, Transaction, UserRule


def matches_text(rule: Rule, text: str) -> bool:
    """Does the rule's pattern match this text?"""
    if rule.match == "exact":
        return text == rule.pattern

    if rule.match == "prefix":
        # "SHELL" matches "SHELL OIL" but not "SHELLYS BAKERY".
        if not text.startswith(rule.pattern):
            return False
        next_char = text[len(rule.pattern) : len(rule.pattern) + 1]
        ends_mid_word = rule.pattern[-1].isalnum() and next_char.isalnum()
        return not ends_mid_word

    if rule.match == "contains":
        return contains_whole_words(text, rule.pattern)

    # rule.match == "regex"
    return re.search(rule.pattern, text) is not None


def contains_whole_words(text: str, words: str) -> bool:
    """`CAR WASH` is in `JOES CAR WASH`, but `TOLL` is not in `TOLLIVER`."""
    start = text.find(words)
    while start != -1:
        before = text[start - 1] if start > 0 else " "
        after = text[start + len(words)] if start + len(words) < len(text) else " "
        if not before.isalnum() and not after.isalnum():
            return True
        start = text.find(words, start + 1)
    return False


def matches_sign(rule: Rule, tx: Transaction) -> bool:
    """A "debit" rule only applies to money out, a "credit" rule only to money in."""
    if rule.sign == "debit":
        return tx.is_debit
    if rule.sign == "credit":
        return tx.is_credit
    return True


def first_match(
    rules: list[Rule], text: str, tx: Transaction, ignore_sign: bool = False
) -> Rule | None:
    """Return the first rule (most specific) that matches, or None."""
    for rule in rules:
        sign_ok = ignore_sign or matches_sign(rule, tx)
        if sign_ok and matches_text(rule, text):
            return rule
    return None


def make_evidence(rule: Rule, reason: str) -> Evidence:
    return Evidence(
        layer=rule.layer,
        rule_id=rule.id,
        category=rule.category,
        strength=rule.strength,
        reason=reason,
    )


# Layer 0. Matches the full description, e.g. "TRANSFER TO SAVINGS XXXX4410".
def type_evidence(tx: Transaction, key: MerchantKey, rules: list[Rule]) -> Evidence | None:
    rule = first_match(rules, key.normalized, tx)
    if rule is None:
        return None
    return make_evidence(rule, f"Transaction type: {rule.category}")


# Layer 1. The user's saved "always" rules, matched on the exact merchant key.
def user_evidence(key: MerchantKey, user_rules: list[UserRule]) -> Evidence | None:
    for rule in user_rules:
        if rule.merchant_key == key.key:
            return Evidence(
                layer="user",
                rule_id=rule.id,
                category=rule.category,
                strength="strong",
                reason=f"Your rule: always {rule.merchant_key} as {rule.category}",
            )
    return None


# Layer 2. The merchant dictionary, e.g. SHELL -> Fuel.
def merchant_evidence(tx: Transaction, key: MerchantKey, rules: list[Rule]) -> Evidence | None:
    rule = first_match(rules, key.key, tx)
    if rule is None:
        return None
    if rule.action == "review":
        return make_evidence(rule, rule.reason)
    if rule.reason:
        return make_evidence(rule, f"{rule.reason}: {rule.category}")
    return make_evidence(rule, f"Known merchant {rule.pattern} is {rule.category}")


# Layer 3. Keywords anywhere in the merchant key, e.g. "CAR WASH".
def keyword_evidence(tx: Transaction, key: MerchantKey, rules: list[Rule]) -> Evidence | None:
    rule = first_match(rules, key.key, tx)
    if rule is None:
        return None
    if rule.strength == "strong":
        return make_evidence(rule, f"Keyword {rule.pattern} means {rule.category}")
    return make_evidence(rule, f"Keyword {rule.pattern} suggests {rule.category}")
