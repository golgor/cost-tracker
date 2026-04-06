---
type: bmad-distillate
sources:
  - "_bmad-output/planning-artifacts/epics.md"
downstream_consumer: "developer maintenance reference"
created: "2026-04-03"
---

> **Divergence note (March 2026):** Audit logging (FR43-44) removed in PR #24. Group/membership management (FR39-42) simplified in PR #28: no groups, no admin roles, no setup wizard. See `docs/architecture/` for current system state.

## Epic 1: Project Foundation & First Login

**Goal:** Running, authenticated app where two partners log in to a shared household — infrastructure backbone for all subsequent epics.

- **1.1 — Project Scaffold & Dev Infrastructure** (done)
  - Hexagonal directory layout: `app/domain/`, `app/adapters/sqlalchemy/`, `app/web/`, `app/auth/`, `app/dependencies.py`, `app/main.py`, `app/settings.py`, `app/logging.py`
  - pydantic-settings (ADR-010); `.env.example` committed; structlog JSON in prod / console in dev (ADR-008)
  - `/health` endpoint reports app + DB connectivity
  - CI split by path (ADR-009): code (pytest/ruff/ty), docs (markdownlint), docker (build)
  - Docker multi-stage: Tailwind CSS build stage → production image, no Node.js at runtime
  - `architecture_test.py`: domain import purity, `queries/` read-only, no `utils.py`/`helpers.py`
  - PostgreSQL `_test` database (auto-derived from `DATABASE_URL`); CI provisions PostgreSQL service container; `mise run test:integration` for local runs
  - CI schema drift check: `alembic upgrade head` output must match `Base.metadata.create_all()`
  - Stories 1.1 and 1.2 have zero code overlap; can be developed in parallel

- **1.2 — Design System & Base Templates** (done)
  - Design tokens: primary `#C27B5A`, bg `#FAF8F6`, stone neutrals, settlement amber `#D4913A`, balance green `#2E7D5B`, red `#B8453A`; green/red reserved exclusively for balance direction
  - System font stack; no custom web fonts; cards: `p-4`/`rounded-lg`/`shadow-sm`
  - HTMX transitions: 150ms opacity fade via `htmx-swapping`/`htmx-settling`; `prefers-reduced-motion` suppresses; `hx-disabled-elt` prevents double-submit
  - Responsive: mobile bottom nav (4 items + FAB) vs desktop top nav (`md:` 768px breakpoint); binary CSS switch, no intermediate tablet layout
  - WCAG AA: 4.5:1 body contrast, 44×44px touch targets, visible focus rings (primary accent)

- **1.3 — OIDC Authentication & Session Management** (done)
  - Authentik + Authlib; signed cookie session with `user_id` + `issued_at`
  - First OIDC login → auto-provision User from claims (name, email)
  - CSRF token required on all state-changing requests; missing token → 403
  - Auth dependency injects `user_id: int` (not framework request context)
  - `UserPort` protocol / `SqlAlchemyUserAdapter` / `UserRow`; `UserRow` never leaves adapter boundary
  - `contract_test.py`: `_to_domain(_to_row(user))` round-trip preserves all fields

- **1.4 — Household Group & Setup Wizard** (done; simplified — see divergence note)
  - First user (no active admin) → 3-step setup wizard: confirm profile, create household, configure defaults
  - Second user → auto-provisioned, added to household, no wizard; assigned regular user by default; admin promotion is explicit in-app action
  - Concurrent first-login: unique constraint on group membership → exactly one succeeds as creator
  - `GroupPort` / `SqlAlchemyGroupAdapter` / `GroupRow`; contract test required
  - First Alembic migration: `users`, `groups`, membership join table

- **1.5 — Audit Infrastructure & Domain Skeleton** (done; audit logging later removed PR #24)
  - `AuditPort` in `app/domain/`: `log(action, actor_id, entity_type, entity_id, changes)`; `changes` = `{"field": {"old": ..., "new": ...}}` (only changed fields)
  - `SqlAlchemyAuditAdapter` → `audit_logs` table / `AuditRow` with single `changes` JSON column
  - `uow.audit` on `UnitOfWork`; audit adapter shares same DB session as data changes (atomic)
  - `changes.py` helpers: `snapshot_new()` for creates, `compute_changes()` for updates; no audit row if nothing changed
  - `dependencies.py` is sole wiring point for all adapters
  - `DOMAIN_ERROR_MAP` in `app/main.py`: maps `DomainError` subclasses to HTTP responses; no per-route try/except
  - `creator_id` and `payer_id` are separate fields on Expense — documented here, implemented in Epic 2

- **1.6 — Admin Bootstrap & User Lifecycle Core** (done; admin roles simplified per PR #28)
  - First active admin: auto-assigned when no active admin exists
  - Deactivated users: remain in DB for traceability; excluded from default pickers; OIDC login denied until reactivated
  - Last-admin protection: deactivation rejected with domain error
  - All lifecycle mutations (`promote`, `demote`, `deactivate`, `reactivate`) call `uow.audit.log()`

- **1.7 — Group-Safe Deactivation & Visibility Rules** (done; simplified per PR #28)
  - Deactivation blocked if user is member of any active/unsettled group
  - Historical records (expense, settlement, audit) preserve original user reference; UI indicates deactivated status
  - Deactivated users excluded from all default pickers; viewable only via explicit admin filter

- **1.8 — Admin Interface for User & Role Management** (done; simplified per PR #28)
  - Admin dashboard: User Management + Audit Log screens; accessible only to admin role (non-admin → 403)
  - User table: name, email, role, status, inline action buttons (promote/demote/deactivate/reactivate)
  - Last-admin demotion blocked: "Cannot demote the last active admin"
  - Deactivation of user in active groups blocked: "Cannot deactivate user who is part of active groups"
  - Audit log: chronological entries with timestamp, actor, action, target, previous values; filterable by user/action/date

---

## Epic 2: Daily Expense Tracking

**Goal:** Partners capture, view, edit, and delete shared expenses with a live balance — daily-use core.

- **2.1 — Expense Domain Model & Create Expense** (done)
  - `Expense` dataclass fields: `id`, `group_id`, `amount (Decimal)`, `description`, `date`, `creator_id`, `payer_id`, `currency` (group default), `split_type` (even only in E2), `status` (pending)
  - `ExpenseRow` → `expenses` table: `amount (NUMERIC)`, `creator_id (FK)`, `payer_id (FK)` — creator_id ≠ payer_id by design
  - `contract_test.py`: round-trip preserves all fields including `Decimal` precision
  - Money: always `Decimal`, never float; zero and negative amounts rejected
  - Currency stored as display label only — no conversion in MVP (FR46)
  - Epic 2 balance = direct 50/50 calculation; Epic 4 Story 4.2 migrates to `expense_splits` table sum

- **2.2 — Dashboard with Balance Bar & Expense Feed** (done)
  - Balance bar: horizontal red/green, partner names + amounts, authenticated user's side emphasized; zero-balance → "All square!"
  - "This Month" widget: total shared expenses current calendar month; non-tappable
  - Feed: newest first, grouped by date with day separator headers; paid-by initials badges (warm clay vs dusty sage)
  - All data via read-only `queries/` (ADR-006); balance query designed for Epic 4 extension

- **2.3a — Mobile Expense Capture** (done)
  - FAB: 56px min, centered, elevated above bottom nav; tap → bottom sheet
  - Bottom sheet: feed partially visible behind; amount field auto-focused with `inputmode='decimal'`
  - Post-save: `primary-50` fade transition on new expense card; balance bar updates; loading state local to submit button
  - Validation errors: field-level persistent inline (no toasts, no auto-dismiss); form data preserved

- **2.3b — Desktop Expense Capture & Batch Entry** (done)
  - Always-visible sidebar form on expenses view; "+ Add Expense" button in top nav scrolls/focuses it
  - "Save & Next": form clears, cursor returns to amount; paid-by persists between entries
  - Tab flow: Amount → Where/What → Date → Split → Paid-by → Save

- **2.4 — Expense Detail View & Edit** (done)
  - Detail shows: description, amount, date, "Created by [name]" and "Paid by [name]" (FR8/FR42 display), per-member split amounts, currency, status
  - Edit via dedicated detail page (not inline, not modal); same form pattern as capture
  - Settled expense: read-only, no edit controls; edit use case calls `uow.audit.log()` with previous values

- **2.5 — Expense Deletion & Feed Filtering** (done)
  - Delete confirmation dialog: shows "Where/What" + amount; danger button placed away from cancel
  - Settled expenses: no delete action available
  - Filter bar: collapsible, date range + paid-by toggle; applies via HTMX partial swap
  - Content vocabulary: "shared expenses", "balance", "settle up" — never "debt" / "owe"; field label "Where / What"

---

## Epic 3: Monthly Settlement

**Goal:** Review unsettled expenses, confirm a settlement with reference ID, browse history — closing the monthly loop.

- **3.1 — Settlement Domain Model & Review Initiation** (done)
  - `Settlement` dataclass fields: `id`, `group_id`, `reference_id`, `settled_by_id`, `total_amount (Decimal)`, `transfer_direction`, `expense_ids (list)`, `settled_at`
  - `SettlementRow` → `settlements` table + `settlement_expenses` join table; contract test required
  - Settlement review is stateless — no data persisted until confirmation; abandon = no side effects
  - Pending expenses grouped by week with collapsible sections; all selected by default; gift expenses auto-excluded
  - Unsettled count dashboard widget: escalates with amber bg + "Time to settle up?" when >30 expenses or 6+ weeks
  - Balance calculation < 500ms for ~50 expenses (NFR3)

- **3.2 — Settlement Confirmation with Concurrent Protection** (done)
  - `SELECT FOR UPDATE` on selected expenses within transaction (FR22)
  - Concurrent conflict → `DomainError` via `DOMAIN_ERROR_MAP`; stale expense ID (deleted) → `DomainError`, user must restart
  - Reference ID format: `SET-{year}-{month}-{short-hash}`
  - On confirm: all included expenses → settled + immutable; settlement record persisted; `uow.audit.log()` called; all atomic
  - Settled expense immutability enforced at DB level (NFR4)
  - Settlement undo deferred post-MVP; if added later must reverse immutability flag + create compensating audit entry
  - CI integration test: two concurrent confirmations for overlapping expenses → exactly one succeeds

- **3.3 — Settlement Success & Reference ID** (done)
  - Amber-themed success screen (step 3); reference ID prominent; copy-to-clipboard with immediate visual feedback
  - Summary view: reference ID, transfer direction (neutral language), total, date confirmed, included expenses list (read-only)

- **3.4 — Settlement History & Drill-Down** (done)
  - History cards: date, reference ID (copyable), total, transfer direction
  - Drill-down: all included expenses as read-only; each shows settlement reference ID
  - Paginated by settlement period; HTMX partial loading
  - Dashboard settlement history widget: most recent settlement(s) summary; tappable → full history

- **3.5 — Expense View Toggle & Audit Trail View** (done; audit trail removed PR #24)
  - Unsettled/Settled toggle via HTMX partial swap; default = Unsettled
  - Settled view: read-only, shows settlement reference ID per expense
  - Audit trail view (removed PR #24): was to show chronological state changes per expense/settlement with previous values

---

## Epic 4: Split Modes & Expense Lifecycle

**Goal:** All four split modes + expense lifecycle actions (gift, notes) — go-live gate for real household use.

- **4.1 — Split Mode Domain Logic & Validation** (done)
  - `SplitType` enum: `even`, `shares`, `percentage`, `exact`
  - `ExpenseSplit` dataclass: `expense_id`, `user_id`, `amount (Decimal)`, `share_value (Decimal, nullable)`
  - `expense_splits` table: unique constraint on `(expense_id, user_id)`
  - Rounding: all modes round to cent; remainder assigned to payer (NFR6)
  - `percentage`: must sum to exactly 100% → `DomainError` if not
  - `exact`: must sum to expense total → `DomainError` if not
  - All amounts use `Decimal` — no floats in calculation path
  - Data migration: backfill even-split rows for all existing Epic 2 expenses (amount/2, remainder to payer) so balance query can safely switch to `expense_splits` sum

- **4.2 — Split Mode UI & Expense Form Update** (done)
  - Split selector in capture/edit form: Even (default), Shares, Percentage, Exact
  - Dynamic preview of split amounts as user types
  - Inline validation errors: "Percentages must sum to 100% (currently X%)" / "Amounts must sum to €X.XX (currently €Y.YY)"
  - Balance query updated to sum from `expense_splits` table (replaces Epic 2 50/50 calculation)

- **4.3 — Gift Expense Status** (done)
  - Status model: `pending` (in balance + settlement) / `gift` (excluded from both) / `settled` (immutable); no "accepted" status in MVP
  - Either co-admin can set gift status on any expense (FR5/FR41)
  - Gift ↔ pending toggle allowed on unsettled expenses; settled expenses immutable
  - Settlement review: deselecting expense = UI state only, not a status change
  - Gift expenses excluded from balance and auto-excluded from settlement review

- **4.4 — Expense Notes** (done)
  - `expense_notes` table: `id`, `expense_id (FK)`, `author_id (FK)`, `content (text)`, `created_at`, `updated_at`
  - Notes displayed chronologically with author + timestamp; own notes show edit/remove actions
  - All add/edit/remove operations call `uow.audit.log()` with previous content
  - Settled expense notes: read-only; no add/edit/remove

---

## Epic 5: Recurring Cost Engine & Polish

**Goal:** Automate predictable costs, add search and nav polish — complete product for daily household use. (Epic in progress per project memory)

- **5.1 — Recurring Definition Domain Model & Registry View** (done)
  - `RecurringDefinition` dataclass fields: `id`, `group_id`, `name`, `amount (Decimal)`, `frequency` (monthly/quarterly/yearly/every_n_months), `interval_months` (for every_n_months), `next_due_date`, `payer_id`, `split_type`, `split_config`, `category (optional)`, `icon (optional)`, `auto_generate (bool, default false)`, `active (bool, default true)`, `created_at`
  - `recurring_definitions` table; contract test required
  - Normalized monthly cost calculated on create (e.g., yearly €120 → €10/mo)
  - Registry: card layout (Wallos-inspired), Active/Paused tabs, sorted by next_due_date soonest first, summary bar at top

- **5.2 — Edit, Pause & Manage Recurring Definitions** (done)
  - Edit form: primary fields always visible; schedule fields below separator; optional fields behind "More options"; "Every N months" reveals interval input
  - Edit-forward semantics: banner "Changes apply to future expenses only. Existing expenses in the feed are unchanged"
  - Pause toggle: active ↔ paused; paused definitions excluded from reminders and auto-generation
  - On reactivation: `next_due_date` recalculated if it has passed
  - On removal: existing generated expenses remain unchanged in feed

- **5.3 — Expense Generation & Recurring Indicators** (done)
  - Auto-generate trigger: on-login check for overdue definitions (no background process in MVP); known limitation: delayed if no login after billing date
  - Generation accepts `current_date` parameter (not `datetime.now()` internally) — enables test simulation
  - Idempotency: DB unique constraint `uq_expenses_definition_billing_period` on `(recurring_definition_id, billing_period)` → prevents duplicate generation if both partners log in simultaneously
  - `expenses` table additions: `recurring_definition_id (nullable FK)`, `billing_period`
  - Feed indicator: recurring icon + tappable "from [definition name]" link; auto-generated adds green "auto" badge; deleted-definition link becomes inert

- **5.4 — Dashboard Widgets & Reminders** (done)
  - Recurring widget: "{N} active · €{total}/mo" with upcoming due dates; tappable → registry; empty state if none
  - Reminder cards: manual-mode definitions due within 7 days; show icon, name, amount, frequency, who pays, "Create Expense" button; disappear after expense created
  - Normalized monthly total = sum of all active definitions normalized to monthly
  - All dashboard data via read-only `queries/` (ADR-006)

- **5.5a — Keyword Search** (done)
  - Searches description + notes via HTMX partial swap; matches highlight search term; response < 200ms

- **5.5b — Navigation Polish & Responsive Refinements** (done)
  - "Recurring" nav item activated; all 4 nav items functional on mobile and desktop
  - Desktop sidebar layout polished; all pages < 1s full load, < 200ms HTMX partials

---

## Deferred / Post-MVP

- **FR45 — Full CRUD API (`/api/v1/`):** per ADR-007; added post-MVP without domain changes; HTMX/page routes serve MVP
