# Testing Follow-ups — Household Setup (PostgreSQL-only)

This note captures pending test-related follow-ups for the household setup changes after moving fully to PostgreSQL tests and removing SQLite dependency.

## Context

During the setup/group implementation pass, several code paths and contracts were updated:

- Group/membership adapter behavior
- First-login auto-provision flow
- Setup wizard defaults (including `tracking_threshold`)
- Domain error mapping
- Mutation use cases and audit calls

Because the test environment moved away from SQLite and fixture contracts changed, test updates should be completed in a focused pass.

---

## 1) Align adapter contract test session typing with SQLModel Session

### Why
Adapter constructors expect a SQLModel session type. Current contract tests may annotate with SQLAlchemy ORM `Session`, which can produce type-check failures (even if runtime works).

### Follow-up
- In `tests/adapters/contract_test.py`:
  - Use `sqlmodel.Session` for type hints in test function parameters.
  - Keep fixture name (`db_session`) unchanged if already wired in `tests/conftest.py`.

### Expected outcome
- Static type checks stop reporting session-type mismatch on adapter construction.

---

## 2) Add/verify Group + Membership contract tests

### Why
Story acceptance explicitly requires adapter contract coverage for group-related mapping and persistence behavior.

### Follow-up
Ensure `tests/adapters/contract_test.py` contains coverage for:

- Group save/retrieve round-trip:
  - `name`
  - `default_currency`
  - `default_split_type`
  - `tracking_threshold`
- Membership add/retrieve round-trip:
  - `user_id`
  - `group_id`
  - `role`
  - `joined_at`
- `get_by_user_id` returns expected group for a member
- Adapter boundary checks:
  - adapter returns public domain models, not ORM rows

### Expected outcome
- Contract coverage includes all newly introduced household fields and membership behavior.

---

## 3) Add race/idempotency tests around membership provisioning

### Why
Auto-provision and setup flows now rely on duplicate-membership handling for idempotency under concurrent login/setup events.

### Follow-up
Add tests in domain/web layers to assert:

- Duplicate membership add raises/handles `DuplicateMembershipError` as intended.
- OIDC callback path is idempotent when membership already exists.
- Setup step-2 race path behaves safely when admin/group already appears mid-flow.

### Expected outcome
- Concurrency-sensitive behavior is regression-protected.

---

## 4) Add setup wizard tests for threshold + validations

### Why
Step 3 now accepts and validates `tracking_threshold`; step 2 includes stricter household-name bounds.

### Follow-up
Add/extend web route tests (e.g., `tests/web/setup_routes_test.py`) to cover:

- Step 2:
  - reject household name `< 2` chars
  - reject household name `> 100` chars
- Step 3:
  - reject invalid `default_currency`
  - reject invalid `default_split_type`
  - reject `tracking_threshold < 1` or `> 365`
  - persist valid `tracking_threshold` and redirect to dashboard

### Expected outcome
- Wizard form validations and persistence path are fully tested.

---

## 5) Verify global domain-error mapping behavior

### Why
New domain errors were introduced/used by group flows and should map to expected HTTP statuses.

### Follow-up
Add integration/web tests that assert handler mapping for:

- `DuplicateHouseholdError` → 409
- `DuplicateMembershipError` → 409
- `GroupNotFoundError` → 404
- `UnauthorizedGroupActionError` → 403

### Expected outcome
- Domain exception semantics are stable and visible at HTTP boundary.

---

## 6) Audit logging rule conformance tests (if/when audit adapter is concrete)

### Why
Mutation use cases call `uow.audit.log()`. A no-op audit implementation exists currently, but behavior should be validated once concrete persistence/log sink is added.

### Follow-up
- Add unit tests that assert mutation use cases invoke audit with expected action and payload keys.
- If introducing persistent audit storage, add adapter contract tests for audit rows/events.

### Expected outcome
- Architectural rule “mutations must audit” is enforced by tests.

---

## 7) Fixture/lint cleanup for PostgreSQL-only test setup

### Why
After fixture refactors, lint and type noise can appear (import ordering, stale imports, long lines, fixture return-type annotations).

### Follow-up
In `tests/conftest.py` and related files:

- Remove unused imports.
- Ensure import order/format matches project linting.
- Keep URL construction wrapped to satisfy line-length rules.
- Ensure fixture annotations reflect yielded types correctly.

### Expected outcome
- `mise run lint` clean.
- No avoidable fixture-level type/lint failures.

---

## Suggested execution order

1. Session typing + fixture/lint cleanup  
2. Group/membership contract tests  
3. Wizard validation tests (`household_name`, `tracking_threshold`)  
4. Race/idempotency tests  
5. Domain error mapping tests  
6. Audit behavior tests (or mark deferred until concrete audit adapter)

---

## Exit criteria

- `mise run test` passes (PostgreSQL-only suite)
- `mise run lint` passes
- Household/group acceptance-critical behavior has direct test coverage
- No remaining TODOs for story 1.4 test obligations