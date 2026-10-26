"""Request bodies and response shaping for the API."""

from pydantic import BaseModel, Field

from app.models import Decision, Transaction


class TransactionPatch(BaseModel):
    category: str | None = None
    business_pct: int | None = Field(default=None, ge=0, le=100)


class RuleCreate(BaseModel):
    merchant_key: str
    category: str
    apply_to_existing: bool = True


def row(tx: Transaction, decision: Decision) -> dict:
    """One table row for the UI: the transaction plus its decision."""
    data = tx.model_dump(mode="json")
    data["decision"] = decision.model_dump(mode="json", exclude={"transaction_id"})
    return data
