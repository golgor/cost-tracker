# Audit System Removal — Implementation Guide

**Status:** Approved for implementation in a dedicated session/PR
**Reason:** The audit system adds ~960 LOC of complexity (12% of codebase) for a purely observational feature. It tightly couples every adapter, port, and use case via `actor_id` threading. Structured logging via `structlog` (already in the project) provides equivalent visibility with zero coupling.

---

## Scope Summary

| Layer | Files affected | What changes |
|-------|---------------|--------------|
| Delete entirely | 3 files | `audit_adapter.py`, `changes.py`, `audit.html` template |
| Domain models | `models.py`, `ports.py` | Remove `AuditEntry`, `AuditPort`, `actor_id` from all port signatures |
| ORM models | `orm_models.py` | Remove `AuditRow` |
| Adapters (5) | `user_adapter.py`, `group_adapter.py`, `expense_adapter.py`, `settlement_adapter.py`, `recurring_adapter.py` | Remove audit constructor param, all `snapshot_*`/`compute_changes` calls, all `self._audit.log()` calls, `actor_id` from method signatures |
| Unit of Work | `unit_of_work.py` | Remove audit adapter wiring |
| Use cases (5) | `users.py`, `groups.py`, `expenses.py`, `settlements.py`, `recurring.py` | Remove `actor_id` parameter from all functions |
| Web handlers (6) | `admin.py`, `auth.py`, `expenses.py`, `recurring.py`, `setup.py`, `api_internal.py` | Remove `actor_id=` from use case calls |
| View models | `view_models.py` | Remove `AuditEntryViewModel` |
| Queries | `admin_queries.py` | Remove `get_recent_audit_entries()`, keep `get_all_users()` |
| Settings | `settings.py` | Remove `SYSTEM_ACTOR_ID` |
| Tests | `audit_adapter_test.py` + references in other tests | Delete audit tests, remove `actor_id` from test helpers |
| Migration | `001_initial_schema.py` | Remove `audit_logs` table and indexes (squash opportunity) |

---

## Step-by-Step Execution Order

Work bottom-up to avoid import errors at each step.

### Step 1: Delete dedicated audit files

```
rm app/adapters/sqlalchemy/audit_adapter.py
rm app/adapters/sqlalchemy/changes.py
rm app/templates/admin/audit.html
rm tests/adapters/audit_adapter_test.py
```

### Step 2: Domain layer — remove AuditEntry, AuditPort, actor_id from ports

**`app/domain/models.py`:**
- Delete the `AuditEntry` class

**`app/domain/ports.py`:**
- Delete the `AuditPort` class
- Remove `audit: AuditPort` from `UnitOfWorkPort`
- Remove `*, actor_id: int` from every mutation method in every port:
  - `UserPort`: `save`, `promote_to_admin`, `demote_to_user`, `deactivate`, `reactivate`
  - `GroupPort`: `save`, `update`, `add_member`
  - `ExpensePort`: `save`, `update`, `delete`, `save_splits`
  - `SettlementPort`: `save`
  - `RecurringDefinitionPort`: `save`, `update`, `soft_delete`

### Step 3: ORM models — remove AuditRow

**`app/adapters/sqlalchemy/orm_models.py`:**
- Delete `AuditRow` class
- Remove from `__all__`

### Step 4: Unit of Work — remove audit wiring

**`app/adapters/sqlalchemy/unit_of_work.py`:**
- Remove `SqlAlchemyAuditAdapter` import
- Remove `self.audit = SqlAlchemyAuditAdapter(session)`
- Change all adapter constructors from `XxxAdapter(session, self.audit)` to `XxxAdapter(session)`

### Step 5: Adapters — remove audit from all 5 adapters

For each adapter (`user_adapter.py`, `group_adapter.py`, `expense_adapter.py`, `settlement_adapter.py`, `recurring_adapter.py`):

1. Remove imports: `SqlAlchemyAuditAdapter`, `compute_changes`, `snapshot_new`, `snapshot_deleted`
2. Remove `audit` from `__init__` parameters and `self._audit`
3. Remove `*, actor_id: int` from all method signatures
4. Remove all `changes = snapshot_new(...)`, `changes = compute_changes(...)`, `changes = snapshot_deleted(...)` lines
5. Remove all `self._audit.log(...)` calls and their surrounding `if changes:` guards
6. In `expense_adapter.py` `update()`: remove the `if changes:` guard around flush — always flush
7. In `expense_adapter.py` note methods: remove `previous_content` capture lines (only used for audit)

### Step 6: Use cases — remove actor_id threading

For each use case module:

**`users.py`:** Remove `*, actor_id: int` param from all 6 functions. Remove `actor_id=actor_id` from `uow.users.*()` calls.

**`groups.py`:** Remove `actor_id=user_id` and `actor_id=actor_user_id` from `uow.groups.*()` calls.

**`expenses.py`:** Remove `actor_id` from `update_expense()` and `delete_expense()`. Remove `actor_id=creator_id` and `actor_id=actor_id` from `uow.expenses.*()` calls.

**`settlements.py`:** Remove `actor_id=settled_by_id` from `uow.settlements.save()`.

**`recurring.py`:** Remove `actor_id` param from all 7 functions. Remove `actor_id=actor_id` from all `uow.recurring.*()` and `uow.expenses.*()` calls.

### Step 7: Web handlers — remove actor_id passing

**`admin.py`:** Remove audit page endpoint, `AuditEntryViewModel` import, `get_recent_audit_entries` import. Remove `actor_id=actor_id` from use case calls (keep `actor_id` variable for `_check_admin_access`).

**`auth.py`:** Remove `actor_id=` from `provision_user()` and `bootstrap_first_admin()` calls.

**`expenses.py`:** Remove `actor_id=` from all use case calls.

**`recurring.py`:** Remove `actor_id=` from all use case calls.

**`setup.py`:** Remove `actor_id=` from all use case calls.

**`api_internal.py`:** Remove `actor_id` from `run_auto_generation()` and downstream calls. Remove `settings.SYSTEM_ACTOR_ID` usage.

### Step 8: View models and queries

**`view_models.py`:** Delete `AuditEntryViewModel` class.

**`admin_queries.py`:** Delete `get_recent_audit_entries()` function and `AuditRow` import. Keep `get_all_users()`.

**`queries/__init__.py`:** Remove any audit-related re-exports.

### Step 9: Settings

**`settings.py`:** Remove `SYSTEM_ACTOR_ID: int = 0` field.

### Step 10: Migration

Remove `audit_logs` table from migration 001. This pairs well with the migration squash recommendation (F-07).

### Step 11: Tests

- Delete `tests/adapters/audit_adapter_test.py`
- Search all test files for `actor_id` and remove from use case calls
- Search for `AuditRow`, `AuditEntry`, `audit` imports and remove
- Update `tests/conftest.py` if it references audit

### Step 12: Replace with structured logging (optional)

Add `structlog` calls in use cases where visibility matters:

```python
# In use_cases/expenses.py
import structlog
logger = structlog.get_logger()

def create_expense(uow, group_id, amount, ...):
    ...
    saved = uow.expenses.save(expense)
    logger.info("expense_created", expense_id=saved.id, amount=str(amount), group_id=group_id)
    return saved
```

This is optional — the request logging middleware already captures all HTTP requests.

---

## Verification Checklist

After implementation:

- [ ] `grep -r "actor_id" app/` — should only appear in `user_adapter.py` (for `deactivated_by_user_id` field) and `auth.py` (for `actor_id` in OIDC context, if any)
- [ ] `grep -r "audit" app/` — should return zero results (except comments if any)
- [ ] `grep -r "changes\." app/adapters/` — should return zero results
- [ ] `uv run ruff check app/` — passes
- [ ] `uv run ruff format --check app/` — passes
- [ ] `uv run pytest tests/ -v` — all tests pass
- [ ] `uv run python -c "from app.main import app"` — app starts without errors

---

## Impact on Other Review Findings

Removing audit resolves or simplifies these findings from the code review:

- **F-05** (audit snapshots skip falsy values) — eliminated
- **F-13** (inconsistent audit logging patterns) — eliminated
- **F-10** (ports accept `*Public` as input) — simpler to fix without `actor_id` noise
- **F-33** (duplicate query in save_splits) — audit log call after the duplicate query is removed; the duplicate query itself still needs fixing separately
