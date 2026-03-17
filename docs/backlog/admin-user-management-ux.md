# Backlog: Admin User Management UX Design & Web Layer

**Status:** Blocked — missing UX design
**Origin:** Story 1.6, Task 7 (incomplete)
**Priority:** Medium — backend is functional, but no user-facing UI exists

## Context

Story 1.6 implemented the backend for admin user lifecycle management (promote, demote,
deactivate, reactivate). The domain layer, adapters, use cases, and audit logging are all in place
and tested.

However, Task 7 was not fully delivered:

> - Add admin-only routes/actions for promote, demote, deactivate, reactivate
> - **Add/extend forms for lifecycle mutations with CSRF protection** ← missing
> - **Surface clear domain error messages in UI** ← missing
> - Ensure route handlers remain thin (no ad hoc domain try/except anti-patterns)

The current `app/web/admin.py` has POST endpoints that return JSON responses. This does not match
the project's HTMX + Jinja2 architecture — endpoints should return HTML partials for `hx-swap`.

## What's Missing

### 1. UX Design (blocked)

No UX design exists for admin user management. The `docs/ux-design/` docs cover:

- Setup wizard (first-run flow)
- Expense entry and management
- Settlement flow
- Dashboard

But nothing covers:

- Admin user list page (viewing all users with their roles and status)
- User action buttons (promote/demote/deactivate/reactivate)
- Confirmation dialogs for destructive actions (deactivation)
- Error feedback (e.g., "Cannot deactivate last admin")
- Deactivated user visual treatment in lists

The UX docs also describe both partners as "co-admins with equal permissions" (executive-summary.md),
which conflicts with the admin/user role hierarchy that Story 1.6 implemented. This needs a UX
decision.

### 2. Templates (blocked on UX design)

Once the UX design is defined, the following templates need to be created:

- `templates/admin/users.html` — admin user list page
- `templates/admin/_user_row.html` — HTMX partial for a single user row (swapped after actions)
- Confirmation patterns for destructive actions (inline or modal)

### 3. Web Layer Rework (blocked on templates)

`app/web/admin.py` needs to be updated to follow the project's HTMX patterns:

- Replace `JSONResponse` with `TemplateResponse` returning HTML partials
- Replace `_check_admin_access` helper with a `get_admin_user` FastAPI dependency in
  `dependencies.py`
- The `_check_admin_access` function raises `HTTPException` directly — this should be a domain
  error (`UnauthorizedGroupActionError` or a new `AdminRoleRequired`) routed through
  `DOMAIN_ERROR_MAP`
- Add GET `/admin/users` route for the user list page

## Definition of Done

- [ ] UX design for admin user management added to `docs/ux-design/`
- [ ] `templates/admin/` directory with user list page and row partial
- [ ] `app/web/admin.py` returns HTMX partials, not JSON
- [ ] Admin access enforced via FastAPI dependency, not inline helper
- [ ] `_check_admin_access` replaced with domain error through global handler
- [ ] CSRF tokens included in all forms
- [ ] Tests for admin routes (template assertions, HTMX responses)

## References

- Story 1.6 artifact: `_bmad-output/implementation-artifacts/1-6-admin-bootstrap-and-user-lifecycle-core.md`
- Architecture patterns: `docs/architecture/implementation-patterns-consistency-rules.md`
  (HTMX Response Formats, Route Handler Pattern)
- UX design gap: `docs/ux-design/executive-summary.md` describes "co-admins with equal
  permissions" — conflicts with admin/user role hierarchy