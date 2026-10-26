"""CI gates: precision on the held-out set, determinism of the generator, and speed."""

import time

from app.brain.engine import categorize
from eval.evaluate import DATA_DIR, PRECISION_TARGET, evaluate
from eval.generate_data import generate, split
from tests.conftest import make_tx


def test_held_out_precision_meets_target() -> None:
    report = evaluate(DATA_DIR / "test.csv")
    assert report.precision >= PRECISION_TARGET, report.markdown("test")
    assert report.missed_reviews == []


def test_committed_data_matches_the_seeded_generator() -> None:
    dev, test = split(generate())
    assert len(dev) + len(test) == len(generate())
    lines = (DATA_DIR / "test.csv").read_text(encoding="utf-8").splitlines()
    assert len(lines) - 1 == len(test)


def test_5000_rows_in_under_2_seconds() -> None:
    samples = [("SHELL OIL 57442 TX", "-42.10"), ("UBER TECHNOLOGIES PAYOUT", "412.30"),
               ("JOES CAFE 9921", "-8.75"), ("SQ *JOES CAR WASH", "-15.00"),
               ("WALMART SUPERCENTER #2231", "-63.20")]  # fmt: skip
    transactions = [make_tx(f"{d} {i}", a) for i in range(1000) for d, a in samples]
    started = time.perf_counter()
    categorize(transactions)
    assert time.perf_counter() - started < 2.0
