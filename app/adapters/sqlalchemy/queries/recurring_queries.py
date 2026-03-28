"""Read-only queries for the recurring definitions registry view."""

from typing import Any

from sqlmodel import Session, select

from app.adapters.sqlalchemy.orm_models import RecurringDefinitionRow, UserRow
from app.domain.models import RecurringFrequency
from app.domain.recurring import normalized_monthly_cost

_FREQUENCY_LABELS: dict[RecurringFrequency, str] = {
    RecurringFrequency.MONTHLY: "monthly",
    RecurringFrequency.QUARTERLY: "quarterly",
    RecurringFrequency.SEMI_ANNUALLY: "semi-annually",
    RecurringFrequency.YEARLY: "yearly",
    RecurringFrequency.EVERY_N_MONTHS: "every N months",
}


def _get_payer_map(session: Session, payer_ids: set[int]) -> dict[int, UserRow]:
    """Fetch user rows for the given payer IDs."""
    if not payer_ids:
        return {}
    rows = session.exec(select(UserRow).where(UserRow.id.in_(payer_ids))).all()  # type: ignore[union-attr]
    return {row.id: row for row in rows if row.id is not None}


def _initials(display_name: str) -> str:
    """Extract up to two uppercase initials from a display name."""
    parts = display_name.strip().split()
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _build_definition_view(
    row: RecurringDefinitionRow,
    payer_map: dict[int, UserRow],
) -> dict[str, Any]:
    """Build a precomputed view model dict for a single recurring definition row."""
    payer = payer_map.get(row.payer_id)
    payer_display_name = payer.display_name if payer else "Unknown"
    payer_initials = _initials(payer_display_name) if payer else "?"

    frequency = (
        row.frequency
        if isinstance(row.frequency, RecurringFrequency)
        else RecurringFrequency(row.frequency)
    )
    monthly_cost = normalized_monthly_cost(row.amount, frequency, row.interval_months)

    frequency_label = _FREQUENCY_LABELS.get(frequency, frequency.value.lower())
    if frequency == RecurringFrequency.EVERY_N_MONTHS and row.interval_months:
        frequency_label = f"every {row.interval_months} months"

    return {
        "id": row.id,
        "name": row.name,
        "amount": row.amount,
        "frequency": row.frequency,
        "frequency_label": frequency_label,
        "interval_months": row.interval_months,
        "next_due_date": row.next_due_date,
        "payer_id": row.payer_id,
        "payer_display_name": payer_display_name,
        "payer_initials": payer_initials,
        "split_type": row.split_type,
        "split_config": row.split_config,
        "category": row.category,
        "auto_generate": row.auto_generate,
        "is_active": row.is_active,
        "currency": row.currency,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "deleted_at": row.deleted_at,
        # Precomputed boolean flags for template visibility (no comparisons in templates)
        "is_auto_generate": row.auto_generate,
        "is_manual_mode": not row.auto_generate,
        # Pre-formatted normalized monthly cost string
        "normalized_monthly_cost": str(monthly_cost),
    }


def get_active_definitions(
    session: Session,
    group_id: int,
) -> list[dict[str, Any]]:
    """Fetch active (not paused, not deleted) recurring definitions for the registry.

    Returns view model dicts with precomputed display fields.
    Sorted by next_due_date ascending (soonest first).
    """
    statement = (
        select(RecurringDefinitionRow)
        .where(
            RecurringDefinitionRow.group_id == group_id,
            RecurringDefinitionRow.deleted_at.is_(None),  # type: ignore[union-attr]
            RecurringDefinitionRow.is_active.is_(True),  # type: ignore[union-attr]
        )
        .order_by(RecurringDefinitionRow.next_due_date)  # type: ignore[arg-type]
    )
    rows = session.exec(statement).all()

    payer_ids = {row.payer_id for row in rows}
    payer_map = _get_payer_map(session, payer_ids)

    return [_build_definition_view(row, payer_map) for row in rows]


def get_paused_definitions(
    session: Session,
    group_id: int,
) -> list[dict[str, Any]]:
    """Fetch paused (is_active=False, not deleted) recurring definitions.

    Returns view model dicts with precomputed display fields.
    """
    statement = (
        select(RecurringDefinitionRow)
        .where(
            RecurringDefinitionRow.group_id == group_id,
            RecurringDefinitionRow.deleted_at.is_(None),  # type: ignore[union-attr]
            RecurringDefinitionRow.is_active.is_(False),  # type: ignore[union-attr]
        )
        .order_by(RecurringDefinitionRow.name)  # type: ignore[arg-type]
    )
    rows = session.exec(statement).all()

    payer_ids = {row.payer_id for row in rows}
    payer_map = _get_payer_map(session, payer_ids)

    return [_build_definition_view(row, payer_map) for row in rows]


def get_registry_summary(
    session: Session,
    group_id: int,
) -> dict[str, Any]:
    """Compute the summary bar data for the registry view.

    Returns:
        Dict with:
        - active_count (int)
        - has_active_definitions (bool) — for template visibility check
        - active_plural (str) — "" or "s" for pluralization
        - total_monthly_cost (str, formatted Decimal)
        - currency (str) — currency code of the group's recurring definitions
    """
    from app.adapters.sqlalchemy.orm_models import GroupRow

    group_row = session.get(GroupRow, group_id)
    currency = group_row.default_currency if group_row else "EUR"

    statement = select(RecurringDefinitionRow).where(
        RecurringDefinitionRow.group_id == group_id,
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
