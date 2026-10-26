"""Request bodies and response shaping for the API."""

from pydantic import BaseModel

from app.models import Decision, Transaction


# business_pct is range-checked in the service, so the API answers `invalid_business_pct`.
class TransactionPatch(BaseModel):
    category: str | None = None
    business_pct: int | None = None


class BulkTransactionPatch(TransactionPatch):
    transaction_ids: list[str]


class RuleCreate(BaseModel):
    merchant_key: str
    category: str
    apply_to_existing: bool = True


def row(tx: Transaction, decision: Decision) -> dict:
    """One table row for the UI: the transaction plus its decision."""
    data = tx.model_dump(mode="json")
    data["decision"] = decision.model_dump(mode="json", exclude={"transaction_id"})
    return data
