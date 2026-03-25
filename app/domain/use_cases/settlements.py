"""Settlement domain use cases."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.errors import EmptySettlementError, SettlementError, StaleExpenseError
from app.domain.models import ExpensePublic, ExpenseStatus, SettlementPublic
from app.domain.ports import UnitOfWorkPort


@dataclass
class SettlementCalculation:
    """Result of settlement calculation."""

    total_amount: Decimal
    transfer_from_user_id: int
    transfer_to_user_id: int
    transfer_message: str


def calculate_settlement(
    expenses: list[ExpensePublic],
    user_display_names: dict[int, str],
) -> SettlementCalculation:
    """Calculate settlement totals and transfer direction.

    For even splits (50/50), calculates net position per member.
    Returns who pays whom and how much.
    """
    if not expenses:
        return SettlementCalculation(
            total_amount=Decimal("0"),
            transfer_from_user_id=0,
            transfer_to_user_id=0,
            transfer_message="Select expenses to see total",
        )

    # Get unique payers from expenses
    payer_ids = set(expense.payer_id for expense in expenses)

    # If only one payer in all expenses, they're owed half the total
    if len(payer_ids) == 1:
        payer_id = list(payer_ids)[0]
        total_amount = sum((expense.amount for expense in expenses), Decimal("0"))
        amount_owed = total_amount / Decimal("2")

        # Find the other user from display_names (who owes the payer)
        other_users = [uid for uid in user_display_names if uid != payer_id]
        if other_users:
            from_id = other_users[0]  # The other person owes money
            to_id = payer_id  # The payer receives money
        else:
            # Fallback - shouldn't happen in practice
            from_id = to_id = payer_id
            amount_owed = Decimal("0")

        from_name = user_display_names.get(from_id, f"User {from_id}")
        to_name = user_display_names.get(to_id, f"User {to_id}")

        if amount_owed == 0:
            transfer_message = "No payment needed"
        else:
            transfer_message = f"{from_name} pays {to_name}"

        return SettlementCalculation(
            total_amount=amount_owed,
            transfer_from_user_id=from_id,
            transfer_to_user_id=to_id,
            transfer_message=transfer_message,
        )

    # Multiple payers - calculate net balance
    balances: dict[int, Decimal] = {}

    for expense in expenses:
        half = expense.amount / Decimal("2")
        payer_id = expense.payer_id

        # Payer paid full amount but is only responsible for half
        # So payer is owed half by other members
        balances[payer_id] = balances.get(payer_id, Decimal("0")) + half

        # Track the other members who owe this half
        for other_id in payer_ids:
            if other_id != payer_id:
                balances[other_id] = balances.get(other_id, Decimal("0")) - half

    # Find who owes money (negative balance) and who is owed money (positive balance)
    member_ids = list(balances.keys())

    if len(member_ids) >= 2:
        # Sort by balance - person with most negative balance owes money
        sorted_balances = sorted(balances.items(), key=lambda x: x[1])

        if sorted_balances[0][1] < 0 and sorted_balances[-1][1] > 0:
            # Person with negative balance pays person with positive balance
            from_id = sorted_balances[0][0]  # Lowest (negative) balance - owes money
            to_id = sorted_balances[-1][0]  # Highest (positive) balance - is owed money
            amount = abs(sorted_balances[0][1])  # Amount to transfer
        else:
            # All balanced or all positive (edge cases)
            from_id = member_ids[0]
            to_id = member_ids[1] if len(member_ids) > 1 else member_ids[0]
            amount = Decimal("0")
    else:
        # Only one member - no transfer needed
        from_id = member_ids[0] if member_ids else 0
        to_id = from_id
        amount = Decimal("0")

    # Build transfer message
    from_name = user_display_names.get(from_id, f"User {from_id}")
    to_name = user_display_names.get(to_id, f"User {to_id}")

    if amount == 0:
        transfer_message = "No payment needed - expenses are balanced"
    else:
        transfer_message = f"{from_name} pays {to_name}"

    return SettlementCalculation(
        total_amount=amount,
        transfer_from_user_id=from_id,
        transfer_to_user_id=to_id,
        transfer_message=transfer_message,
    )


def generate_reference_id(uow: UnitOfWorkPort, group_id: int) -> str:
    """Generate unique human-readable reference ID.

    Format: "March 2025" or "March 2025 (2)" if duplicate exists.
    """
    now = datetime.now(UTC)
    base = now.strftime("%B %Y")  # e.g., "March 2025"

    # Check for existing settlements with same base reference
    existing = uow.settlements.list_by_group(group_id)
    existing_refs = {s.reference_id for s in existing}

    if base not in existing_refs:
        return base

    # Find next available number
    counter = 2
    while f"{base} ({counter})" in existing_refs:
        counter += 1

    return f"{base} ({counter})"


def confirm_settlement(
    uow: UnitOfWorkPort,
    *,
    group_id: int,
    expense_ids: list[int],
    settled_by_id: int,
    user_display_names: dict[int, str],
    reference_id: str | None = None,
) -> SettlementPublic:
    """Confirm a settlement and mark expenses as settled.

    Args:
        uow: Unit of work for transaction boundary
        group_id: Group being settled
        expense_ids: IDs of expenses to include
        settled_by_id: User confirming the settlement
        user_display_names: Mapping of user IDs to display names
        reference_id: Optional custom reference (auto-generated if None)

    Returns:
        The created settlement

    Raises:
        EmptySettlementError: If expense_ids is empty
        StaleExpenseError: If an expense is already settled
    """
    # Validation
    if not expense_ids:
        raise EmptySettlementError()

    # Fetch and validate expenses
    expenses: list[ExpensePublic] = []
    for expense_id in expense_ids:
        expense = uow.expenses.get_by_id(expense_id)
        if expense is None:
            raise SettlementError(f"Expense {expense_id} no longer exists")
        if expense.status == ExpenseStatus.SETTLED:
            raise StaleExpenseError(expense_id)
        expenses.append(expense)

    # Calculate settlement
    calculation = calculate_settlement(expenses, user_display_names)

    # Generate reference_id if not provided
    if reference_id is None:
        reference_id = generate_reference_id(uow, group_id)

    # Create settlement
    settlement = SettlementPublic(
        id=-1,  # Will be set by DB
        group_id=group_id,
        reference_id=reference_id,
        settled_by_id=settled_by_id,
        total_amount=calculation.total_amount,
        transfer_from_user_id=calculation.transfer_from_user_id,
        transfer_to_user_id=calculation.transfer_to_user_id,
        settled_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )

    # Save settlement (this also updates expense statuses via adapter)
    saved = uow.settlements.save(settlement, expense_ids, actor_id=settled_by_id)

    return saved
