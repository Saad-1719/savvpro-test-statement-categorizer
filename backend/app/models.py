"""Domain models shared by ingest, brain, reports and the API.

Money is always Decimal. Negative amounts are money out.
"""

import re
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Strength = Literal["strong", "medium", "weak"]
Status = Literal["auto", "review", "excluded"]
Kind = Literal["income", "expense", "contra", "personal", "excluded"]


class Category(BaseModel):
    name: str
    kind: Kind
    tax_line: str | None = None  # line on the tax form (see rules/tax_form.yaml); None = not on it
    tax_line_label: str | None = None
    mixed_use: bool = False  # needs a business-use percentage before it counts


class Transaction(BaseModel):
    id: str  # stable hash of file name + row number
    source_file: str
    row_number: int
    date: date
    raw_description: str
    amount: Decimal
    account: str  # "checking" | "credit_card"
    bank_category: str | None = None
    flags: list[str] = Field(default_factory=list)  # duplicate, outside_tax_year

    @property
    def is_debit(self) -> bool:
        return self.amount < 0

    @property
    def is_credit(self) -> bool:
        return self.amount > 0


class MerchantKey(BaseModel):
    key: str
    normalized: str  # full description, upper-cased with whitespace collapsed
    processor: str | None = None
    refund_marker: bool = False


class Rule(BaseModel):
    id: str
    layer: str
    match: Literal["exact", "prefix", "contains", "regex"]
    pattern: str
    action: Literal["categorize", "review"] = "categorize"
    category: str | None = None
    reason: str | None = None  # required for review rules; optional label otherwise
    strength: Strength = "strong"
    sign: Literal["debit", "credit", "any"] = "any"
    max_amount: Decimal | None = None  # compared with abs(amount)
    priority: int = 0  # higher wins inside a layer, before match type and length

    @model_validator(mode="after")
    def _check(self) -> "Rule":
        if self.action == "categorize" and not self.category:
            raise ValueError(f"rule {self.id}: categorize rule needs a category")
        if self.action == "review" and not self.reason:
            raise ValueError(f"rule {self.id}: review rule needs a reason")
        if self.match == "regex":
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(f"rule {self.id}: bad regex: {exc}") from exc
        return self


class Evidence(BaseModel):
    layer: str  # type | user | merchant | keyword | bank_category
    rule_id: str
    category: str | None  # None for a review rule
    strength: Strength
    reason: str


class Decision(BaseModel):
    transaction_id: str
    merchant_key: str
    status: Status
    category: str | None
    suggestion: str | None = None
    reason: str
    rule_id: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    refund_of: str | None = None
    business_pct: int | None = None
    decided_by: Literal["brain", "user"] = "brain"


class UserRule(BaseModel):
    id: str
    merchant_key: str
    category: str


class SkippedRow(BaseModel):
    row_number: int
    reason: str


class FileSummary(BaseModel):
    file_name: str
    layout: str
    rows_read: int
    rows_skipped: list[SkippedRow]
    junk_rows_before_header: int
    footer_rows: int
    duplicates: int
    outside_tax_year: int
    date_from: date | None
    date_to: date | None
    money_in: Decimal
    money_out: Decimal
