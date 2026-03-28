# User Deactivation Removal — Implementation Guide

**Status:** Approved for implementation in a dedicated session/PR
**Reason:** The OIDC provider (Authentik) is the source of truth for user lifecycle. Removing a user from Authentik blocks them at next login. The in-app `is_active` deactivation is a redundant layer that adds ~300 LOC of complexity across domain, adapters, use cases, web handlers, and tests — with no practical value for a trusted household app.

**What stays:** Admin promote/demote (app-level role management that OIDC doesn't handle).

---

## What to remove

### Domain models (`app/domain/models.py`)

Remove from `UserBase`:
- `is_active: bool = Field(default=True)`
- `deactivated_at: datetime | None = Field(default=None)`
- `deactivated_by_user_id: int | None = Field(default=None)`

### Domain errors (`app/domain/errors.py`)

Delete these error classes entirely:
- `LastActiveAdminDeactivationForbidden`
- `UserHasActiveGroupMembershipError`
- `DeactivatedUserAccessDenied`
- `UserAlreadyDeactivated`
- `UserAlreadyActive`

### Error map (`app/main.py`)

Remove these entries from `DOMAIN_ERROR_MAP`:
- `LastActiveAdminDeactivationForbidden: 409`
- `UserHasActiveGroupMembershipError: 409`
- `DeactivatedUserAccessDenied: 403`
- `UserAlreadyDeactivated: 409`
- `UserAlreadyActive: 409`

### Domain ports (`app/domain/ports.py`)

Remove from `UserPort`:
- `def deactivate(self, user_id: int) -> UserPublic`
- `def reactivate(self, user_id: int) -> UserPublic`

### Use cases (`app/domain/use_cases/users.py`)

Delete these functions entirely:
- `deactivate_user()`
- `reactivate_user()`

Simplify `provision_user()` — remove the `is_active` check:
```python
def provision_user(uow, oidc_sub, email, display_name):
    return uow.users.save(oidc_sub=oidc_sub, email=email, display_name=display_name)
```

Simplify `deactivate_user` reference in `bootstrap_first_admin` — the `count_active_admins()` method currently filters by `is_active`. After removal, rename to `count_admins()` and remove the `is_active` filter.

### User adapter (`app/adapters/sqlalchemy/user_adapter.py`)

Delete these methods:
- `deactivate()`
- `reactivate()`

Simplify `count_active_admins()` → rename to `count_admins()`:
```python
def count_admins(self) -> int:
    from sqlalchemy import func
    statement = (
        select(func.count())
        .select_from(UserRow)
        .where(UserRow.role == UserRole.ADMIN)
    )
    return self._session.exec(statement).first() or 0
```

Similarly rename `get_active_admins()` → `get_admins()` and remove the `is_active` filter.

Update `_to_public()` — remove the three fields from the mapping.

### ORM models (`app/adapters/sqlalchemy/orm_models.py`)

`UserRow` inherits from `UserBase`, so removing fields from `UserBase` removes them from the ORM model automatically. No separate change needed here.

### Migration (`alembic/versions/001_initial_schema.py`)

Remove from the `users` table:
- `sa.Column("is_active", ...)`
- `sa.Column("deactivated_at", ...)`
- `sa.Column("deactivated_by_user_id", ...)`
- `sa.ForeignKeyConstraint(["deactivated_by_user_id"], ...)`

Remove these indexes:
- `ix_users_is_active`
- `ix_users_deactivated_at`

### Admin web handler (`app/web/admin.py`)

Delete these endpoints:
- `deactivate_confirm_dialog()` (GET `/admin/users/{id}/deactivate-confirm`)
- `deactivate_user()` (POST `/admin/users/{id}/deactivate`)
- `reactivate_user()` (POST `/admin/users/{id}/reactivate`)

In `admin_users_page()`, the `active_admin_count` logic can be simplified — it currently counts active admins. Change to count all admins (since there's no active/inactive distinction anymore).

Update `UserRowViewModel` in `app/web/view_models.py`:
- Remove `status_label`, `status_badge_color`, `status_filter` fields
- Remove `show_deactivate`, `show_reactivate` button flags
- The `show_demote` flag changes from `is_active and is_admin and can_mutate_admin` to just `is_admin and can_mutate_admin`
- `show_promote` changes from `is_active and not is_admin` to `not is_admin`

### Admin templates

- `app/templates/admin/users.html` — remove deactivate/reactivate buttons and status badge column
- `app/templates/admin/_user_row.html` — same
- `app/templates/admin/_deactivate_confirm.html` — delete entirely

### Auth callback (`app/web/auth.py`)

Remove the `DeactivatedUserAccessDenied` catch block in the OIDC callback handler. The `provision_user()` call becomes a simple save without any deactivation check.

### Queries

Check `app/adapters/sqlalchemy/queries/admin_queries.py` — `get_all_users()` returns `UserPublic` which will no longer have the deactivation fields after model change. No separate fix needed.

### Tests

Search and update all test files:
- `tests/domain/users_test.py` — delete deactivation/reactivation test cases
- `tests/web/admin_ui_test.py` — remove deactivation UI tests, status badge assertions
- `tests/web/admin_mutations_test.py` — remove deactivation mutation tests
- `tests/adapters/contract_test.py` — remove deactivation field round-trip tests if any
- Any test that sets `is_active=False` or calls `deactivate_user()`/`reactivate_user()`

Search patterns:
```bash
grep -r "is_active\|deactivat\|reactivat\|UserAlreadyDeactivated\|UserAlreadyActive\|DeactivatedUserAccessDenied\|LastActiveAdminDeactivation" tests/
```

---

## Verification checklist

After implementation:

- [ ] `grep -r "is_active" app/` — should only appear in comments (if any)
- [ ] `grep -r "deactivat" app/` — zero results
- [ ] `grep -r "reactivat" app/` — zero results
- [ ] `ruff check app/ tests/` — passes
- [ ] `ruff format --check app/ tests/` — passes
- [ ] `uv run pytest tests/ -v` — all tests pass
- [ ] `uv run ty check app/` — no errors (warnings OK)

---

## Impact on other review findings

- **F-35** (deactivated user check in middleware) — eliminated entirely, no longer relevant
- Admin UI becomes simpler — only promote/demote actions remain
- `UserRowViewModel` simplifies significantly
- Domain error hierarchy shrinks by 5 error classes
