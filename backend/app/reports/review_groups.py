"""Group the Needs Review rows by merchant, so one fix can cover a whole group."""

from decimal import Decimal

from app.models import Decision, Transaction


def group_review_rows(
    transactions: list[Transaction], decisions: dict[str, Decision]
) -> list[dict]:
    groups = {}  # merchant key -> group
    for tx in transactions:
        decision = decisions[tx.id]
        if decision.status != "review":
            continue

        key = decision.merchant_key
        if key not in groups:
            groups[key] = {
                "merchant_key": key,
                "count": 0,
                "total": Decimal("0"),
                "reason": decision.reason,  # reason of the first row in the group
                "suggestion": None,
                "transaction_ids": [],
            }
        group = groups[key]
        group["count"] += 1
        group["total"] += tx.amount
        group["transaction_ids"].append(tx.id)
        if group["suggestion"] is None:
            group["suggestion"] = decision.suggestion

    # Biggest groups first: fixing them clears the most rows.
    def biggest_first(group: dict) -> tuple[int, Decimal]:
        return (-group["count"], -abs(group["total"]))

    ordered = sorted(groups.values(), key=biggest_first)
    for group in ordered:
        group["total"] = str(group["total"])
    return ordered
