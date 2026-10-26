"""Totals per category, the unreviewed amount and the tax-form summary.

What counts:
  - Only rows with status "auto" (decided by the brain or by the user).
  - A refund is subtracted from the category it refunds (a Shell refund lowers Fuel).
  - Phone & Data only counts its business share, and only once the user gives a %.
Totals are "final" only when nothing is left to review and every phone row has a %.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.models import Category, Decision, Transaction

ZERO = Decimal("0")


def to_cents(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_summary(
    transactions: list[Transaction],
    decisions: dict[str, Decision],
    categories: dict[str, Category],
) -> dict:
    net_amount = {}  # category -> signed sum (income positive, spending negative)
    deductible = {}  # category -> positive amount that can be deducted
    unreviewed_amount = ZERO
    unreviewed_count = 0
    phone_rows_missing_pct = 0

    for tx in transactions:
        decision = decisions[tx.id]

        if decision.status == "review":
            unreviewed_amount += abs(tx.amount)
            unreviewed_count += 1
            continue
        if decision.status != "auto":
            continue  # transfers, card payments, duplicates: not counted

        category_name = decision.category
        if category_name == "Refund" and decision.refund_of:
            category_name = decision.refund_of  # the refund lowers that category

        net_amount[category_name] = net_amount.get(category_name, ZERO) + tx.amount

        category = categories[category_name]
        if category.kind != "expense":
            continue

        spent = -tx.amount  # spending is negative in the statement; make it positive
        if category.mixed_use:
            if decision.business_pct is None:
                phone_rows_missing_pct += 1
                continue
            spent = spent * decision.business_pct / 100
        deductible[category_name] = deductible.get(category_name, ZERO) + spent

    # One line per category that has any rows, in taxonomy order.
    totals = []
    for name, category in categories.items():
        if name not in net_amount:
            continue
        line = {
            "category": name,
            "kind": category.kind,
            "amount": to_cents(net_amount[name]),
            "deductible_amount": None,
            "tax_line": category.tax_line,
        }
        if category.kind == "expense":
            # A refund bigger than the spending can't make a deduction negative.
            line["deductible_amount"] = to_cents(max(deductible.get(name, ZERO), ZERO))
        totals.append(line)

    income_total = ZERO
    deductible_total = ZERO
    for line in totals:
        if line["kind"] == "income":
            income_total += line["amount"]
        if line["deductible_amount"] is not None:
            deductible_total += line["deductible_amount"]

    return {
        "totals": totals,
        "income_total": to_cents(income_total),
        "deductible_total": to_cents(deductible_total),
        "unreviewed_amount": to_cents(unreviewed_amount),
        "unreviewed_count": unreviewed_count,
        "phone_missing_pct_count": phone_rows_missing_pct,
        "is_final": unreviewed_count == 0 and phone_rows_missing_pct == 0,
        "tax_form_lines": tax_form_lines(totals, categories),
    }


def tax_form_lines(totals: list[dict], categories: dict[str, Category]) -> list[dict]:
    """Group the totals by tax-form line. Income counts in full, expenses by deductible amount.

    Several categories can share a line: Fuel, Tolls and Insurance are all line 9.
    The form itself is named in rules/tax_form.yaml.
    """
    lines = {}  # line number -> {"line", "label", "amount"}
    for total in totals:
        category = categories[total["category"]]
        if not category.tax_line:
            continue  # Personal, Transfer, ... are not on the form

        if category.kind == "income":
            value = total["amount"]
        else:
            value = total["deductible_amount"]

        number = category.tax_line
        if number not in lines:
            lines[number] = {"line": number, "label": category.tax_line_label, "amount": ZERO}
        lines[number]["amount"] += value
    return list(lines.values())
