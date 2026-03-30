"""Shared row-to-public model conversions for read-only query modules.

These mirror the adapter _to_public() methods but are standalone functions
so query modules can convert rows without instantiating adapters.
"""

from app.adapters.sqlalchemy.orm_models import (
    ExpenseRow,
    SettlementRow,
    SettlementTransactionRow,
)
from app.domain.models import ExpensePublic, SettlementPublic, SettlementTransactionPublic


def expense_row_to_public(row: ExpenseRow) -> ExpensePublic:
    """Convert expense ORM row to public domain model."""
    if row.id is None or row.created_at is None or row.updated_at is None:
        raise RuntimeError("Row ID, created_at, and updated_at must not be None for persisted rows")

    return ExpensePublic(
        id=row.id,
        amount=row.amount,
        description=row.description,
        date=row.date,
        creator_id=row.creator_id,
        payer_id=row.payer_id,
        currency=row.currency,
        split_type=row.split_type,
        status=row.status,
        recurring_definition_id=row.recurring_definition_id,
        billing_period=row.billing_period,
        is_auto_generated=row.is_auto_generated,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def settlement_row_to_public(row: SettlementRow) -> SettlementPublic:
    """Convert settlement ORM row to public domain model."""
    if row.id is None or row.created_at is None:
        raise RuntimeError("Row ID and created_at must not be None for persisted rows")

    return SettlementPublic(
        id=row.id,
        reference_id=row.reference_id,
        settled_by_id=row.settled_by_id,
        settled_at=row.settled_at,
        created_at=row.created_at,
    )


def transaction_row_to_public(row: SettlementTransactionRow) -> SettlementTransactionPublic:
    """Convert settlement transaction ORM row to public domain model."""
    if row.id is None:
        raise RuntimeError("Row ID must not be None for persisted rows")

    return SettlementTransactionPublic(
        id=row.id,
        settlement_id=row.settlement_id,
        from_user_id=row.from_user_id,
        to_user_id=row.to_user_id,
        amount=row.amount,
    )
