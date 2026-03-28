# Code Review Findings — Architecture Improvements

Architecture improvements from the production readiness code review (PR #22).
All four findings have been implemented (PR #27).

## F-12: Recurring queries return template-ready dicts instead of domain models

**Priority:** P2
**Files:** `app/adapters/sqlalchemy/queries/recurring_queries.py`, `app/web/view_models.py`, `app/web/recurring.py`

### Problem

`_build_definition_view()` in `recurring_queries.py` returns `dict[str, Any]` with
pre-computed template fields mixed in: `frequency_label`, `payer_display_name`,
`payer_initials`, `is_auto_generate`, `is_manual_mode`, `normalized_monthly_cost`.

This violates the hexagonal architecture — the query layer knows about presentation
concerns. Both `get_active_definitions()` and `get_paused_definitions()` return these
template-ready dicts.

### Fix

1. Make `get_active_definitions()` and `get_paused_definitions()` return
   `list[RecurringDefinitionPublic]` instead of `list[dict]`. Use the adapter's
   `_to_public()` pattern or the shared `mappings.py` approach.

2. Create a `RecurringDefinitionViewModel` in `app/web/view_models.py`:

    ```python
    class RecurringDefinitionViewModel(BaseModel):
        id: int
        name: str
        amount: Decimal
        frequency_label: str        # "monthly", "every 3 months"
        next_due_date: date
        payer_display_name: str
        payer_initials: str
        currency: str
        normalized_monthly_cost: str
        is_auto_generate: bool
        is_manual_mode: bool
        is_active: bool

        @classmethod
        def from_domain(
            cls,
            defn: RecurringDefinitionPublic,
            payer: UserPublic,
        ) -> RecurringDefinitionViewModel:
            ...
    ```

3. In `app/web/recurring.py`, transform domain models to view models before
   passing to templates.

### Scope

The query functions simplify (return domain models), but the view model and handler
transformations need to be built. Templates may need minor adjustments if dict key
names change.

---

## F-18: Business logic in route handlers instead of use cases

**Priority:** P2
**Files:** `app/domain/use_cases/settlements.py`, `app/web/settlements.py`

### Problem

`app/web/settlements.py` performs balance calculation and transaction minimization
directly in the handler (lines 99-108):

```python
balances = calculate_balances(expenses, member_ids, config)
domain_transactions = minimize_transactions(balances)
total_amount = sum(tx.amount.amount for tx in domain_transactions)
transfer_message = format_transfer_message(domain_transactions, display_names)
```

This pattern repeats in `calculate_settlement_total()` and `settlement_confirm_page()`.
Domain logic should live in use cases, not handlers.

### Fix

1. Create a `preview_settlement()` function in `app/domain/use_cases/settlements.py`:

    ```python
    def preview_settlement(
        uow: UnitOfWorkPort,
        expense_ids: list[int],
        member_ids: list[int],
    ) -> tuple[list[SettlementTransaction], dict[int, MemberBalance]]:
        """Calculate settlement preview without persisting anything."""
        expenses = []
        for eid in expense_ids:
            expense = uow.expenses.get_by_id(eid)
            if expense is None:
                raise SettlementError(f"Expense {eid} no longer exists")
            if expense.status == ExpenseStatus.SETTLED:
                raise StaleExpenseError(eid)
            expenses.append(expense)

        config = BalanceConfig()
        balances = calculate_balances(expenses, member_ids, config)
        transactions = minimize_transactions(balances)
        return transactions, balances
    ```

2. The handler simplifies to:

    ```python
    transactions, balances = preview_settlement(uow, expense_ids, member_ids)
    total_amount = sum(tx.amount.amount for tx in transactions)
    transfer_message = format_transfer_message(transactions, display_names)
    ```

### Scope

Small — extract ~15 lines from two handlers into a single use case function. Both
`calculate_settlement_total` and `settlement_confirm_page` call the same function.

---

## F-27: View models only used in admin module

**Priority:** P3
**Files:** `app/web/view_models.py`, `app/web/expenses.py`, `app/web/settlements.py`

### Problem

`app/web/view_models.py` has `UserRowViewModel` and `UserProfileViewModel` — excellent
patterns used only in admin. The rest of the app passes raw domain models or dicts to
templates:

- `expenses.py` passes `ExpensePublic` objects and `users_dict: dict[int, UserPublic]`
- `settlements.py` passes `display_names: dict[int, str]` and raw `ExpensePublic` lists
- `recurring.py` uses dicts from the query layer (see F-12)

### Fix

Create view models for each major template area:

1. **`ExpenseCardViewModel`** — pre-computed: `payer_display_name`, `payer_initials`,
   `is_settled` (bool), `is_gift` (bool), `formatted_amount`, `formatted_date`,
   `currency_symbol`, `show_edit_button`, `show_delete_button`

2. **`SettlementViewModel`** — pre-computed: `reference_id`, `settled_by_name`,
   `formatted_date`, `expense_count`, `transaction_summaries: list[str]`

3. **`BalanceBarViewModel`** — pre-computed: `user_balance_formatted`, `is_positive`,
   `is_negative`, `is_settled`, `transfer_message`

Then transform in handlers before passing to templates. This eliminates any remaining
template logic and makes the "dumb templates" rule easier to enforce.

### Scope

Large — touches many templates and handlers. Best done incrementally: start with
`ExpenseCardViewModel` since `expenses.py` is the biggest file.

---

## F-37: Split `expenses.py` (1241 lines) into sub-modules

**Priority:** P3
**Files:** `app/web/expenses.py`, `app/web/router.py`

### Problem

`app/web/expenses.py` contains 17 endpoint functions covering five distinct areas:

| Group | Functions | ~Lines |
|---|---|---|
| Capture form + split preview | `get_mobile_capture_form`, `get_split_preview` | 120 |
| Create/Update/Delete | `create_expense_endpoint`, `update_expense_endpoint`, `delete_expense_route`, `get_delete_confirmation` | 300 |
| List + filtering | `expenses_list`, `expenses_filtered`, `expenses_balance` | 200 |
| Detail + expand/collapse | `get_expense_detail`, `collapse_expense_detail`, `edit_expense_page` | 200 |
| Notes CRUD | `get_expense_notes`, `add_expense_note`, `edit_expense_note_form`, `edit_expense_note`, `delete_expense_note` | 200 |

### Fix

Split into sub-package `app/web/expenses/`:

```
app/web/expenses/
├── __init__.py          # Re-exports router
├── router.py            # Main router that includes sub-routers
├── crud.py              # create, update, delete endpoints
├── list.py              # list, filtered, balance endpoints
├── detail.py            # detail, collapse, edit page
├── notes.py             # All note CRUD endpoints
└── preview.py           # capture form, split preview
```

Shared helpers (like `_render_expense_notes_section` and template context building)
go in a private `_helpers.py` or stay in the most relevant sub-module.

### Scope

Medium — purely mechanical restructuring, no logic changes. Requires updating imports
in `app/web/router.py` and verifying no circular dependencies.

---

## Recommended implementation order

1. **F-18** (small, contained) — Extract settlement preview use case
2. **F-12** (medium) — Clean up recurring queries, add view model
3. **F-37** (medium, mechanical) — Split `expenses.py` into sub-modules
4. **F-27** (large, incremental) — Add view models for expenses and settlements

F-18 and F-12 are independent of each other. F-37 and F-27 are best done together
for expenses since they touch the same file — splitting first makes the view model
work easier since each sub-module is smaller.
