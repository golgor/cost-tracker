"""Read-only queries for the recurring definitions registry view."""

from typing import Any

from sqlmodel import Session, select

from app.adapters.sqlalchemy.orm_models import RecurringDefinitionRow
from app.domain.models import RecurringDefinitionPublic, RecurringFrequency
from app.domain.recurring import normalized_monthly_cost


def _row_to_public(row: RecurringDefinitionRow) -> RecurringDefinitionPublic:
    """Convert ORM row to public domain model (same pattern as adapter)."""
    if row.id is None:
        raise RuntimeError("Row ID must not be None for persisted rows")

    frequency = (
        row.frequency
        if isinstance(row.frequency, RecurringFrequency)
        else RecurringFrequency(row.frequency)
    )
    from app.domain.models import SplitType

    split_type = (
        row.split_type if isinstance(row.split_type, SplitType) else SplitType(row.split_type)
    )

    return RecurringDefinitionPublic(
        id=row.id,
        name=row.name,
        amount=row.amount,
        frequency=frequency,
        interval_months=row.interval_months,
        next_due_date=row.next_due_date,
        payer_id=row.payer_id,
        split_type=split_type,
        split_config=row.split_config,
        category=row.category,
        auto_generate=row.auto_generate,
        is_active=row.is_active,
        currency=row.currency,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


def get_active_definitions(
    session: Session,
) -> list[RecurringDefinitionPublic]:
    """Fetch active (not paused, not deleted) recurring definitions for the registry.

    Returns domain models sorted by next_due_date ascending (soonest first).
    """
    statement = (
        select(RecurringDefinitionRow)
        .where(
            RecurringDefinitionRow.deleted_at.is_(None),  # type: ignore[union-attr]
            RecurringDefinitionRow.is_active.is_(True),  # type: ignore[union-attr]
        )
        .order_by(RecurringDefinitionRow.next_due_date)  # type: ignore[arg-type]
    )
    rows = session.exec(statement).all()
    return [_row_to_public(row) for row in rows]


def get_paused_definitions(
    session: Session,
) -> list[RecurringDefinitionPublic]:
    """Fetch paused (is_active=False, not deleted) recurring definitions.

    Returns domain models sorted by name.
    """
    statement = (
        select(RecurringDefinitionRow)
        .where(
            RecurringDefinitionRow.deleted_at.is_(None),  # type: ignore[union-attr]
            RecurringDefinitionRow.is_active.is_(False),  # type: ignore[union-attr]
        )
        .order_by(RecurringDefinitionRow.name)  # type: ignore[arg-type]
    )
    rows = session.exec(statement).all()
    return [_row_to_public(row) for row in rows]


# Used by the API layer (/api/v1/).
# Web layer uses compute_registry_stats() from view_models.py instead.
def get_registry_summary(
    session: Session,
) -> dict[str, Any]:
    """Compute the summary bar data for the registry view.

    Returns:
        Dict with:
        - active_count (int)
        - has_active_definitions (bool) — for template visibility check
        - active_plural (str) — "" or "s" for pluralization
        - total_monthly_cost (str, formatted Decimal)
        - currency (str) — currency code from app settings
    """
    from app.settings import settings

    currency = settings.DEFAULT_CURRENCY

    statement = select(RecurringDefinitionRow).where(
        RecurringDefinitionRow.deleted_at.is_(None),  # type: ignore[union-attr]
        RecurringDefinitionRow.is_active.is_(True),  # type: ignore[union-attr]
    )
    rows = session.exec(statement).all()

    active_count = len(rows)
    total = sum(
        normalized_monthly_cost(row.amount, RecurringFrequency(row.frequency), row.interval_months)
        for row in rows
    )

    return {
        "active_count": active_count,
        "has_active_definitions": active_count > 0,
        "active_plural": "s" if active_count != 1 else "",
        "total_monthly_cost": str(total),
        "currency": currency,
    }
