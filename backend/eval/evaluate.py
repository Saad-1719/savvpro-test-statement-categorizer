"""Run the brain on a labeled CSV and report precision, coverage and confusions.

python -m eval.evaluate            # held-out test split
python -m eval.evaluate --split dev
python -m eval.evaluate --gate     # exit 1 if precision < 98% or a trap was auto-decided
"""

import argparse
import csv
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.brain.engine import categorize
from app.ingest.validate import flag_and_summarize
from app.models import Transaction

DATA_DIR = Path(__file__).parent / "data"
PRECISION_TARGET = 0.98


@dataclass
class Report:
    rows: int
    auto: int
    correct_auto: int
    excluded: int
    correct_excluded: int
    review: int
    missed_reviews: list[str] = field(default_factory=list)
    confusions: Counter = field(default_factory=Counter)

    @property
    def precision(self) -> float:
        return self.correct_auto / self.auto if self.auto else 1.0

    @property
    def coverage(self) -> float:
        return self.auto / self.rows if self.rows else 0.0

    @property
    def passed(self) -> bool:
        return self.precision >= PRECISION_TARGET and not self.missed_reviews

    def markdown(self, split: str) -> str:
        lines = [
            f"| Metric ({split} set, {self.rows} rows) | Value |",
            "| --- | --- |",
            f"| Precision of Auto rows | {self.precision:.1%} ({self.correct_auto}/{self.auto}) |",
            f"| Coverage (Auto ÷ all rows) | {self.coverage:.1%} |",
            f"| Sent to Needs Review | {self.review} ({self.review / self.rows:.1%}) |",
            f"| Excluded correctly | {self.correct_excluded}/{self.excluded} |",
            f"| Missed reviews (traps auto-decided) | {len(self.missed_reviews)} |",
        ]
        if self.confusions:
            lines += ["", "| Expected → predicted | Count |", "| --- | --- |"]
            lines += [f"| {pair} | {n} |" for pair, n in self.confusions.most_common(5)]
        return "\n".join(lines)


def load(path: Path) -> tuple[list[Transaction], list[dict]]:
    with path.open(encoding="utf-8") as f:
        labels = list(csv.DictReader(f))
    transactions = [
        Transaction(
            id=f"eval-{i}",
            source_file=path.name,
            row_number=i + 2,
            date=date.fromisoformat(row["date"]),
            raw_description=row["description"],
            amount=Decimal(row["amount"]),
            account="checking",
        )
        for i, row in enumerate(labels)
    ]
    return transactions, labels


def evaluate(path: Path) -> Report:
    transactions, labels = load(path)
    flag_and_summarize(
        transactions,
        file_name=path.name,
        layout="eval",
        skipped=[],
        junk_rows_before_header=0,
        footer_rows=0,
        tax_year=None,
    )
    decisions = categorize(transactions)

    report = Report(
        rows=len(labels), auto=0, correct_auto=0, excluded=0, correct_excluded=0, review=0
    )
    for label, decision in zip(labels, decisions, strict=True):
        expected = (label["expected_status"], label["expected_category"] or None)
        predicted = (decision.status, decision.category)
        if decision.status == "auto":
            report.auto += 1
            if predicted == expected:
                report.correct_auto += 1
            elif label["expected_status"] == "review":
                report.missed_reviews.append(f"{label['description']} -> {decision.category}")
        elif decision.status == "excluded":
            report.excluded += 1
            if predicted == expected:
                report.correct_excluded += 1
        else:
            report.review += 1
        if predicted != expected and decision.status != "review":
            report.confusions[f"{expected[1] or expected[0]} → {predicted[1] or predicted[0]}"] += 1
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("test", "dev"), default="test")
    parser.add_argument("--gate", action="store_true", help="exit 1 below target")
    args = parser.parse_args(argv)

    report = evaluate(DATA_DIR / f"{args.split}.csv")
    print(report.markdown(args.split))
    if report.missed_reviews:
        print("\nMissed reviews:\n" + "\n".join(f"- {m}" for m in report.missed_reviews))
    if args.gate and not report.passed:
        print(f"\nFAILED: precision target is {PRECISION_TARGET:.0%} with 0 missed reviews")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
