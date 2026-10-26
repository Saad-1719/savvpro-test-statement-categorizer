"""Generate labeled fake transactions for one driver year (seeded, so identical every run).

Writes eval/data/dev.csv (70%, used while writing rules) and eval/data/test.csv
(30%, used only by evaluate.py). Labels include the expected status: traps are
labeled `review`, so sending them to review counts as correct.

    python -m eval.generate_data
"""

import csv
import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

SEED = 20251026
ROWS = 500
TAX_YEAR = 2025
DATA_DIR = Path(__file__).parent / "data"
FIELDS = ("date", "description", "amount", "expected_status", "expected_category", "case")

NAMES = ("JOES", "MARIAS", "BIG SKY", "LUCKY", "GREEN LEAF", "DOWNTOWN", "RIVERSIDE", "SUNSET")
STATES = ("TX", "CA", "NY", "FL", "WA", "IL")


@dataclass(frozen=True)
class Template:
    case: str
    descriptions: tuple[str, ...]
    low: float
    high: float
    status: str  # expected status
    category: str  # expected category ("" when review)
    credit: bool = False
    weight: int = 1
    noise: bool = True  # add store numbers / state codes


T = Template
TEMPLATES: tuple[Template, ...] = (
    # Income
    T("payout", ("UBER TECHNOLOGIES PAYOUT", "DOORDASH DASHER PAYOUT", "LYFT DRIVER PAYOUT",
                 "DOORDASH INC PAYMENT", "LYFT INC EARNINGS"),
      150, 1400, "auto", "Platform Income", credit=True, weight=8, noise=False),
    T("tips", ("UBER TIPS PAYOUT", "DOORDASH DASHER TIP", "LYFT BONUS PAYOUT", "UBER QUEST BONUS"),
      10, 120, "auto", "Tips & Bonuses", credit=True, weight=3, noise=False),
    # Vehicle
    T("fuel", ("SHELL OIL", "CHEVRON", "EXXONMOBIL", "BP", "VALERO", "ARCO", "CIRCLE K",
               "SPEEDWAY", "SUNOCO"), 18, 95, "auto", "Fuel", weight=10),
    T("maintenance", ("JIFFY LUBE", "AUTOZONE", "O REILLY AUTO PARTS", "PEP BOYS",
                      "VALVOLINE INSTANT OIL", "FIRESTONE COMPLETE AUTO"),
      12, 400, "auto", "Vehicle Maintenance", weight=4),
    T("car_wash", tuple(f"SQ *{n} CAR WASH" for n in NAMES), 8, 30, "auto",
      "Vehicle Maintenance", weight=3, noise=False),
    T("tolls", ("E-ZPASS REPLENISH", "FASTRAK", "SUNPASS", "PARKMOBILE", "SPOTHERO",
                "CITY OF AUSTIN PARKING", "DOWNTOWN PARKING GARAGE"),
      2, 40, "auto", "Tolls & Parking", weight=5),
    T("insurance", ("GEICO AUTO", "PROGRESSIVE INS", "STATE FARM INSURANCE"),
      90, 180, "auto", "Vehicle Insurance", weight=2, noise=False),
    T("phone", ("VERIZON WRLS", "T-MOBILE", "AT&T *BILL PAYMENT"), 45, 110, "auto",
      "Phone & Data", weight=2, noise=False),
    T("platform_fee", ("DOORDASH FEE", "UBER INSTANT PAY FEE", "LYFT EXPRESS PAY FEE"),
      0.5, 3, "auto", "Platform Fees", weight=3, noise=False),
    T("bank_fee", ("FOREIGN TRANSACTION FEE", "MONTHLY SERVICE FEE", "ATM FEE"),
      1, 15, "auto", "Bank Fees", weight=2, noise=False),
    # Personal
    T("personal", ("UBER *TRIP", "UBER *EATS", "KROGER", "SAFEWAY", "NETFLIX.COM",
                   "STARBUCKS STORE", "CHIPOTLE", "TRADER JOE S"),
      5, 120, "auto", "Personal", weight=8),
    # Excluded
    T("transfer", ("TRANSFER TO SAVINGS", "ONLINE TRANSFER TO SAVINGS", "TRANSFER FROM SAVINGS"),
      100, 800, "excluded", "Transfer", weight=3, noise=False),
    T("card_payment", ("CREDIT CARD PAYMENT NOVA CARD", "NOVA CARD AUTOPAY"),
      200, 900, "excluded", "Card Payment", weight=2, noise=False),
    # Refunds
    T("refund", ("SHELL OIL REFUND", "AUTOZONE REFUND", "JIFFY LUBE RETURN", "CHEVRON REFUND"),
      5, 60, "auto", "Refund", credit=True, weight=2, noise=False),
    # Traps: all must go to review
    T("trap_uber", ("UBER BV", "UBER *PENDING", "UBER ONE MEMBERSHIP"), 5, 25, "review", "",
      weight=3, noise=False),
    T("trap_big_gas", ("SHELL OIL", "CHEVRON", "EXXONMOBIL"), 101, 220, "review", "", weight=3),
    T("trap_deny", ("WALMART SUPERCENTER", "AMAZON MKTPL", "TARGET", "COSTCO WHSE", "BEST BUY"),
      10, 250, "review", "", weight=5),
    T("trap_paypal", ("PAYPAL *XK29Q", "PAYPAL *ZZ881", "PP*7741CODE"), 10, 90, "review", "",
      weight=2, noise=False),
    T("trap_unknown", tuple(f"{n} {kind}" for n in NAMES for kind in ("CAFE", "DINER", "BARBER")),
      4, 60, "review", "", weight=6),
    T("trap_unknown_credit", ("VENMO CASHOUT", "ZELLE FROM SAM", "MOBILE DEPOSIT", "CASH APP"),
      20, 400, "review", "", credit=True, weight=3, noise=False),
    T("trap_conflict", ("SAFEWAY FUEL", "KROGER FUEL CENTER"), 20, 70, "review", "", weight=2),
    T("trap_weak", ("BOBS TIRE SHOP", "QUICK GAS N GO", "PHONE CHARGER KIOSK"), 10, 90,
      "review", "", weight=2),
    T("trap_lookalike", ("SHELLYS SEAFOOD", "BPX CONSULTING", "UBERTI FURNITURE"), 10, 90,
      "review", "", weight=2, noise=False),
)  # fmt: skip


def _noisy(rng: random.Random, description: str, add_noise: bool) -> str:
    text = description
    if add_noise:
        if rng.random() < 0.6:
            text += " " + rng.choice(("", "#")) + str(rng.randint(10, 99999))
        if rng.random() < 0.4:
            text += " " + rng.choice(STATES)
    if rng.random() < 0.2:
        text = text.lower()
    if rng.random() < 0.15:
        text = text.replace(" ", "  ", 1)
    return text


def generate(seed: int = SEED, rows: int = ROWS) -> list[dict]:
    rng = random.Random(seed)
    weights = [t.weight for t in TEMPLATES]
    start = date(TAX_YEAR, 1, 1)
    out: list[dict] = []
    while len(out) < rows:
        template = rng.choices(TEMPLATES, weights)[0]
        value = Decimal(str(round(rng.uniform(template.low, template.high), 2)))
        amount = value if template.credit else -value
        row = {
            "date": (start + timedelta(days=rng.randrange(365))).isoformat(),
            "description": _noisy(rng, rng.choice(template.descriptions), template.noise),
            "amount": str(amount),
            "expected_status": template.status,
            "expected_category": template.category,
            "case": template.case,
        }
        out.append(row)
        if rng.random() < 0.02 and len(out) < rows:  # exact duplicate row
            out.append({**row, "expected_status": "excluded", "expected_category": "",
                        "case": "trap_duplicate"})  # fmt: skip
    return out


def split(rows: list[dict], seed: int = SEED) -> tuple[list[dict], list[dict]]:
    """70/30 split; a duplicate always stays in the same split as its original."""
    rng = random.Random(seed + 1)
    dev: list[dict] = []
    test: list[dict] = []
    for row in rows:
        if row["case"] == "trap_duplicate":
            (test if test and test[-1]["description"] == row["description"] else dev).append(row)
        else:
            (dev if rng.random() < 0.7 else test).append(row)
    return dev, test


def write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    dev, test = split(generate())
    write(DATA_DIR / "dev.csv", dev)
    write(DATA_DIR / "test.csv", test)
    print(f"wrote {len(dev)} dev rows and {len(test)} test rows to {DATA_DIR}")


if __name__ == "__main__":
    main()
