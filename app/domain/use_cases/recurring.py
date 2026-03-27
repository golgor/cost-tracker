"""Recurring definition domain use cases."""

from datetime import date as date_type
from decimal import Decimal

from app.domain.errors import (
    DomainError,
    DuplicateBillingPeriodError,  # noqa: F401 — re-exported for caller convenience
    GroupNotFoundError,
    RecurringDefinitionNotFoundError,
)
from app.domain.models import (
    ExpensePublic,
    ExpenseStatus,
    RecurringDefinitionPublic,
    RecurringFrequency,
    SplitType,
)
from app.domain.ports import UnitOfWorkPort
from app.domain.recurring import advance_due_date, billing_period_for, format_expense_description


def create_recurring_definition(
    uow: UnitOfWorkPort,
    group_id: int,
    actor_id: int,
    name: str,
    amount: Decimal,
    frequency: RecurringFrequency,
    next_due_date: date_type,
    payer_id: int,
    split_type: SplitType = SplitType.EVEN,
    split_config: dict | None = None,
    interval_months: int | None = None,
    category: str | None = None,
    auto_generate: bool = False,
    currency: str | None = None,
) -> RecurringDefinitionPublic:
    """Create a new recurring cost definition.

    Args:
        uow: Unit of work for transaction management
        group_id: ID of the group this definition belongs to
        actor_id: User ID performing the creation
        name: Name of the recurring cost (e.g. "Netflix")
        amount: Amount per billing cycle (must be > 0)
        frequency: Billing frequency (MONTHLY, QUARTERLY, etc.)
        next_due_date: Next billing date
        payer_id: User ID who pays this recurring cost
        split_type: How the cost is split between members
        split_config: Configuration for non-even splits
        interval_months: Required when frequency is EVERY_N_MONTHS (>= 1)
        category: Optional category label
        auto_generate: Whether expenses are created automatically
        currency: Currency code (defaults to group's configured currency)

    Returns:
        The persisted RecurringDefinitionPublic.

    Raises:
        GroupNotFoundError: If the group doesn't exist
        DomainError: If interval_months constraint is violated
    """
    group = uow.groups.get_by_id(group_id)
    if group is None:
        raise GroupNotFoundError(f"Group {group_id} not found")

    _validate_interval_months(frequency, interval_months)

    effective_currency = currency or group.default_currency

    definition = RecurringDefinitionPublic.model_construct(
        id=0,
        group_id=group_id,
        name=name,
        amount=amount,
        frequency=frequency,
        interval_months=interval_months,
        next_due_date=next_due_date,
        payer_id=payer_id,
        split_type=split_type,
        split_config=split_config,
        category=category,
        auto_generate=auto_generate,
        is_active=True,
        currency=effective_currency,
    )

    return uow.recurring.save(definition, actor_id=actor_id)


def update_recurring_definition(
    uow: UnitOfWorkPort,
    definition_id: int,
    actor_id: int,
    name: str | None = None,
    amount: Decimal | None = None,
    frequency: RecurringFrequency | None = None,
    interval_months: int | None = None,
    next_due_date: date_type | None = None,
    payer_id: int | None = None,
    split_type: SplitType | None = None,
    split_config: dict | None = None,
    category: str | None = None,
    auto_generate: bool | None = None,
    is_active: bool | None = None,
    currency: str | None = None,
) -> RecurringDefinitionPublic:
    """Update an existing recurring cost definition.

    Only provided (non-None) fields are updated. Changes apply to future
    expenses only — existing expenses in the feed are unchanged.

    Args:
        uow: Unit of work for transaction management
        definition_id: ID of the definition to update
        actor_id: User ID performing the update
        All other args: Optional new values for each field

    Returns:
        The updated RecurringDefinitionPublic.

    Raises:
        RecurringDefinitionNotFoundError: If definition doesn't exist or is soft-deleted
        DomainError: If interval_months constraint is violated
    """
    definition = uow.recurring.get_by_id(definition_id)
    if definition is None:
        raise RecurringDefinitionNotFoundError(f"Recurring definition {definition_id} not found")

    # Validate interval_months against the effective frequency after update
    effective_frequency = frequency if frequency is not None else definition.frequency
    if frequency is not None or interval_months is not None:
        effective_interval = (
            interval_months if interval_months is not None else definition.interval_months
        )
        _validate_interval_months(effective_frequency, effective_interval)

    return uow.recurring.update(
        definition_id,
        actor_id=actor_id,
        name=name,
        amount=amount,
        frequency=frequency,
        interval_months=interval_months,
        next_due_date=next_due_date,
        payer_id=payer_id,
        split_type=split_type,
        split_config=split_config,
        category=category,
        auto_generate=auto_generate,
        is_active=is_active,
        currency=currency,
    )


def create_expense_from_definition(
    uow: UnitOfWorkPort,
    definition_id: int,
    actor_id: int,
) -> ExpensePublic:
    """Create an expense for the current billing period and advance next_due_date.

    Args:
        uow: Unit of work for transaction management
        definition_id: ID of the recurring definition to generate from
        actor_id: User ID performing the action

    Returns:
        The newly created ExpensePublic.

    Raises:
        RecurringDefinitionNotFoundError: If definition doesn't exist or is deleted
        DuplicateBillingPeriodError: If an expense already exists for this billing period
    """
    definition = uow.recurring.get_by_id(definition_id)
    if definition is None or definition.deleted_at is not None:
        raise RecurringDefinitionNotFoundError(f"Recurring definition {definition_id} not found")

    billing_period = billing_period_for(definition.next_due_date)
    description = format_expense_description(definition.name, billing_period)

    expense = ExpensePublic.model_construct(
        id=0,
        group_id=definition.group_id,
        amount=definition.amount,
        description=description,
        date=definition.next_due_date,
        creator_id=actor_id,
        payer_id=definition.payer_id,
        currency=definition.currency,
        split_type=definition.split_type,
        status=ExpenseStatus.PENDING,
        recurring_definition_id=definition_id,
        billing_period=billing_period,
        is_auto_generated=False,
        created_at=None,  # type: ignore[arg-type]
        updated_at=None,  # type: ignore[arg-type]
    )

    expense_pub = uow.expenses.save(expense, actor_id=actor_id)

    new_due_date = advance_due_date(
        definition.next_due_date,
        definition.frequency,
        definition.interval_months,
    )
    uow.recurring.update(definition_id, actor_id=actor_id, next_due_date=new_due_date)

    return expense_pub


def pause_definition(
    uow: UnitOfWorkPort,
    definition_id: int,
    actor_id: int,
) -> RecurringDefinitionPublic:
    """Pause an active recurring definition.

    Args:
        uow: Unit of work for transaction management
        definition_id: ID of the definition to pause
        actor_id: User ID performing the action

    Returns:
        The updated RecurringDefinitionPublic.

    Raises:
        RecurringDefinitionNotFoundError: If definition doesn't exist or is deleted
    """
    return uow.recurring.update(definition_id, actor_id=actor_id, is_active=False)


def reactivate_definition(
    uow: UnitOfWorkPort,
    definition_id: int,
    actor_id: int,
) -> RecurringDefinitionPublic:
    """Reactivate a paused recurring definition.

    Catches up next_due_date to the next future date if it fell behind while paused.

    Args:
        uow: Unit of work for transaction management
        definition_id: ID of the definition to reactivate
        actor_id: User ID performing the action

    Returns:
        The updated RecurringDefinitionPublic.

    Raises:
        RecurringDefinitionNotFoundError: If definition doesn't exist or is deleted
    """
    definition = uow.recurring.get_by_id(definition_id)
    if definition is None or definition.deleted_at is not None:
        raise RecurringDefinitionNotFoundError(f"Recurring definition {definition_id} not found")

    today = date_type.today()
    next_due = definition.next_due_date
    while next_due < today:
        next_due = advance_due_date(next_due, definition.frequency, definition.interval_months)

    return uow.recurring.update(
        definition_id,
        actor_id=actor_id,
        is_active=True,
        next_due_date=next_due,
    )


def delete_definition(
    uow: UnitOfWorkPort,
    definition_id: int,
    actor_id: int,
) -> None:
    """Soft-delete a recurring definition.

    Args:
        uow: Unit of work for transaction management
        definition_id: ID of the definition to delete
        actor_id: User ID performing the action

    Raises:
        RecurringDefinitionNotFoundError: If definition doesn't exist or is already deleted
    """
    uow.recurring.soft_delete(definition_id, actor_id=actor_id)


def _validate_interval_months(
    frequency: RecurringFrequency,
    interval_months: int | None,
) -> None:
    """Validate interval_months constraint for the given frequency."""
    if frequency == RecurringFrequency.EVERY_N_MONTHS:
        if interval_months is None or interval_months < 1:
            raise DomainError("interval_months must be >= 1 when frequency is EVERY_N_MONTHS")
    elif interval_months is not None:
        raise DomainError("interval_months may only be set when frequency is EVERY_N_MONTHS")
