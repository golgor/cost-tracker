---
type: bmad-distillate
sources:
  - "_bmad-output/planning-artifacts/prd.md"
  - "_bmad-output/planning-artifacts/product-brief-cost-tracker-2026-03-15.md"
  - "_bmad-output/brainstorming/brainstorming-session-2026-03-13-2030.md"
downstream_consumer: "developer onboarding"
created: "2026-04-03"
---

> **Implementation delta (March 2026 plan vs. shipped):** Audit logging (FR43-44) removed in PR #24. Group/membership management (FR39-42) simplified in PR #28 — no groups, no admin roles, no setup wizard. For current system state, see `docs/architecture/`.

## Problem

- Two partners share daily household costs (groceries, fuel, subscriptions, insurance, dining); no tool fits the ongoing relationship model
- Current workflow: receipts in a bowl → monthly sort + manual calculation → error-prone, receipts lost, settlement takes ~1 hour
- Rejected alternatives:
  - Splitwise/Spliit: event splitters, no continuous periodic settlement, can't model "household never closes"
  - YNAB/Actual: individual budgeting, no "who owes whom", no settlement summaries
  - Spreadsheets: no mobile entry, no reference IDs for bank transfers, manual maintenance
  - Old home-automation-hub tool: broken UX (expense entry required navigating to list first), no recurring support, no settlement flow

## Core Concept

- Household cost-sharing is a continuous relationship, not a discrete event — permanent group, periodic settlements that never close the group
- Three interaction loops: (1) daily capture — amount + description in <30 seconds; (2) weekly check-in — dashboard balance + recurring reminders; (3) monthly settlement — review → select → confirm with reference ID → bank transfer
- Philosophy: trust + incentive over enforcement; payer logs because they want money back; only amount required; data quality self-regulates
- Expense log is source of truth; balances calculated on demand (no pre-computed state)

## Users

- **Golgor (on-the-go logger):** tech-savvy dev, logs on phone immediately after purchase; initiates monthly settlement on desktop; also system admin (deploys, monitors, CI/CD); success = 15-second entry, 15-minute monthly settlement, no lost expenses
- **Partner (batch reviewer):** accumulates receipts, enters in batch on laptop (Saturday ritual); not technical; values obvious UI, keyboard-optimized tab order, visual scanning; success = week's receipts entered <15 min, no "what was that charge?" conversations, settlement feels fair
- **Golgor as Admin (secondary hat):** deploys Docker image, monitors structured logs, runs DB backups, updates via CI/CD — same person, different context
- **Guest Friends (MVP2):** vacation trip participants; won't install app or remember credentials between yearly trips; self-interest drives logging; need magic link + frictionless summary at end

## User Journeys

- **Golgor daily:** tap Add Expense → amount + description → save (15 sec, phone in parking lot); recurring costs auto-generate or surface as reminders; end of month: dashboard shows balance → Settle Up → review screen (gift expenses auto-excluded) → confirm → copy reference ID → send to partner; bank transfer arrives next day
- **Partner batch:** weekly laptop session entering receipt pile; adjusts dates via prominent date picker; views dashboard recurring widget (450 EUR/mo, 6 costs); reviews settlement co-located with Golgor; transfers via banking app with reference ID; whole process ~20 min
- **Admin first-run:** push Docker image → ArgoCD deploys to k3s → open app → Authentik OIDC login → setup wizard (no active admin detected) → user auto-provisioned from OIDC claims → household configured → partner logs in → auto-provisioned as regular user → admin grants partner admin rights in-app
- **Guest (MVP2):** receives magic link via text → taps → no install, no account → bookmarks link → adds expenses (self-interest drives accuracy) → end of trip: settlement calculates per-person amounts → magic link shows read-only summary after settlement

## Architecture Constraints (shaped implementation)

- **Hexagonal architecture:** strict service layer; all business logic in services; page routes, HTMX partials, and JSON API all call the same services; no logic in route handlers
- **Three-layer route architecture:** page routes (`/groups/{id}/dashboard`), HTMX partials (same routes, `HX-Request` header), JSON API (`/api/v1/groups/{id}/...`)
- **Server-rendered HTML:** FastAPI + Jinja2; no SPA framework; no Node.js runtime dependency
- **HTMX:** partial page updates (add expense modal, tab switching, widget refresh); HTMX + Tailwind CSS vendored as static files; no CDN dependencies; only ~14KB JS
- **Tailwind v4 CSS-first:** Tailwind CLI runs during Docker image build; no Node.js at runtime
- **Sync SQLAlchemy (no async):** ORM for all DB access; no raw SQL; Alembic for migrations; Postgres for dev and production (same environment)
- **Authentik OIDC:** authentication delegated entirely to Authentik; Authlib as client library; app handles session management (Starlette SessionMiddleware with signed cookies); no passwords, no registration forms in-app
- **Group-scoped routes from day 1:** all endpoints under `/groups/{id}/...`; MVP1 has one group but structure is MVP2-ready
- **Widget-based dashboard:** each section is a self-contained Jinja2 partial with an order attribute; independently refreshable via HTMX
- **ExpenseSplit as relation table:** separate `expense_splits` table (not JSON) for robust querying and settlement calculations via SUM
- **Calculate-on-demand balances:** no pre-computed balance fields; always derived from expense log

## Data Model

```
User: id, name, email, oidc_sub, role (admin|user), is_active
Group: id, name, type (household|event|project), default_currency, default_split_method,
       lifecycle_state (active|settled|archived), start_date, end_date (null=household),
       created_by → User
Member: id, user_id → User, group_id → Group, role (admin|participant), access_method (permanent|magic_link)
Expense: id, amount, currency, date, description (optional), created_by → Member,
         paid_by → Member, status (pending|gift), split_mode (even|shares|percentage|amount),
         group_id → Group, settlement_id → Settlement (null=unsettled)
ExpenseSplit: id, expense_id, member_id, included (bool), share_value, calculated_amount
Note: id, content, author → Member, timestamp, expense_id → Expense
Settlement: id, reference_id (SET-{year}-{month}-{short-hash}), timestamp, group_id → Group
SettlementTransfer: id, settlement_id, from_member → Member, to_member → Member, amount
AuditLog: id, action, actor → Member, timestamp, entity_type, entity_id, details (JSON before/after)
```

- `NUMERIC(19,2)` for all monetary values
- Rounding: round to cent, remainder assigned to payer; per-expense, no accumulation across settlement
- `created_by` vs `paid_by` on Expense: `created_by` automatic (logged-in user), `paid_by` defaults to creator, changeable ("on behalf of" pattern)

## Functional Requirements

### Expense Management
- FR1: Create expense; required: amount; optional: description, date, paid-by, currency
- FR2: Edit any field of an unsettled expense
- FR3: Delete an unsettled expense
- FR4: View expense full details inline (notes, per-member split amounts, status)
- FR5: Gift toggle — any co-admin can toggle; gift excludes from balance but stays visible in feed; pending ↔ gift toggle; delete is separate (removes entirely)
- FR6: Add/edit/remove notes on an expense
- FR7: Prevent modification of expenses in a completed settlement
- FR8: Show creator and payer on each expense in feed and settlement review
- FR46: Currency label per expense, defaulting to group currency; mixed currencies in settlement summed in group default currency; no conversion in MVP1

### Split & Balance
- FR9: 4 split modes: even, shares, percentage, exact amount
- FR10: Calculate current balance on demand from expense log
- FR11: Deterministic rounding — split amounts always sum to expense total
- FR12: Validate split allocations before saving (percentages sum to 100%, amounts sum to total)

### Settlement
- FR13: Initiate settlement review showing all unsettled expenses
- FR14: Deselect individual expenses during review (UI state only — deselected remain pending for future settlements; gift expenses auto-excluded)
- FR15: Confirm settlement → generate unique reference ID (format: `SET-{year}-{month}-{short-hash}` from timestamp + group ID)
- FR16: Copy settlement reference ID for bank transfer
- FR17: View completed settlement summary (transfer direction, amount, reference ID)
- FR18: Browse chronological list of past settlements
- FR19: Drill down into past settlement to see included expenses
- FR20: Settled expenses immutable once settlement confirmed (database-level constraint)
- FR21: Abandon settlement flow at any point without side effects (stateless — nothing persisted until final confirmation)
- FR22: Prevent duplicate settlement confirmation; if two users review concurrently, first to confirm wins; second receives error

### Recurring Costs
- FR23: Create recurring cost definition with: name, amount, frequency (monthly/quarterly/yearly/every N months), next due date, who pays, split method, optional category/icon
- FR24: Dedicated management view showing all definitions with normalized monthly cost (e.g., €600/year → €50/mo), status (active/paused)
- FR25: Edit/pause/reactivate/delete definitions; edit-forward semantics — changes apply to future expenses only; paused = no generation, no reminders, config retained
- FR26: Dashboard reminders when recurring cost is within 7 days of next due date
- FR27: Per-definition auto-generate flag; when on: idempotent service creates pending expense on billing date, pre-filled with definition metadata; when off (default): manual "Create Expense" action with date-picker confirmation modal; generation triggered on dashboard load AND exposed as API endpoint for external cron; system prevents duplicate generation per billing cycle
- FR28: Dashboard shows total normalized monthly recurring cost baseline across all active definitions
- FR29: Expenses generated from recurring definition are linkable back to source definition

### Dashboard & Overview
- FR30: Balance summary (who owes whom, how much)
- FR31: Expense feed sorted newest first
- FR32: Settled/unsettled tab separation
- FR33: Recurring cost widget: active count, normalized monthly total, upcoming due dates
- FR34: Settlement history summary per period (direction + amount)
- FR35: Load additional settled expenses incrementally, paginated by settlement period
- FR36: Navigate from dashboard widgets to detail views (e.g., balance → settle flow)
- FR37: Keyword search on expense feed (matches description and notes)
- FR38: Contextual empty states guide next action; "Settle Up" visible with zero unsettled expenses but shows empty state message rather than hidden

### Group & User Management
- FR39: OIDC login → auto-provision or update app user profile from claims (sub, name, email, preferred_username)
- FR40: Setup wizard when no active admin exists; completing wizard establishes first admin
- FR41: In-app authorization roles: admin and regular user; new auto-provisioned users are regular by default
- FR42: Expense tracks creator separately from payer
- FR47: Admin can deactivate/reactivate users; deactivated users preserved for history, excluded from default pickers
- FR48: Deactivated users cannot access app until admin reactivates
- FR49: Prevent deactivation of last active admin
- FR50: Prevent deactivation of users in active/unsettled groups

### Audit & History (planned; FR43-44 removed in PR #24)
- FR43 (removed): Full audit trail of state-changing actions with actor, timestamp, previous values
- FR44 (removed): User-viewable audit trail per expense/settlement

### System Integration
- FR45: Full CRUD JSON API for all expense, settlement, and group operations (auto-documented via FastAPI /docs)

## Non-Functional Requirements

### Performance
- NFR1: Full page loads < 1 second
- NFR2: HTMX partial responses < 200ms
- NFR3: Settlement balance calculation < 500ms for ~50 expenses

### Data Integrity
- NFR4: Settled expenses immutable at database level
- NFR5: Split amounts always sum exactly to expense total
- NFR6: Rounding strategy — round to cent, remainder to payer
- NFR7: All state-changing operations captured in audit trail

### Reliability
- NFR8: Auto-recovery from container restarts (stateless app, persistent DB); connection pool sized and monitored
- NFR9: DB migrations backwards-compatible and non-destructive
- NFR10: HTMX partial failures display inline errors without breaking page state (`hx-on::response-error` pattern)
- NFR11: Graceful shutdown completing in-flight requests during deployment

### Observability
- NFR12: Structured JSON logs to stdout with request context (method, path, duration, status, request ID)
- NFR13: Health check endpoint reports app and DB connectivity (`/healthz`, `/readyz`, `/startupz`)
- NFR14: Audit trail captures who/what/when/previous value for all expense and settlement state changes

### Security
- NFR15: Auth via OIDC with Authentik as IdP and Authlib as client; app manages sessions (Starlette SessionMiddleware, signed cookies); no passwords, no registration in-app; TLS enforced at infra level
- NFR16: All data on self-hosted infrastructure
- NFR17: API input validated via Pydantic; HTMX form submissions validated explicitly on route handlers
- NFR18: TLS at ingress/Authentik level
- NFR19: SQL injection prevented by ORM — no raw SQL

### Testing & Quality
- NFR20: All tests use PostgreSQL with `_test` database suffix (auto-derived from `DATABASE_URL`; auto-created if missing); integration tests for settlement, data integrity, concurrent ops run against this DB; enforced in GitHub Actions CI before merge
- NFR21: DB backup and recovery strategy documented and tested before Go-Live Gate

## MVP Phasing (historical — delivered as 1a through 1d)

- **MVP1a — Foundation + Core Expense Loop:** scaffolding (FastAPI, Postgres, Docker, CI); OIDC auth (Authentik + Authlib, login/callback/session/logout); auto-provisioning from OIDC claims; app-managed roles (admin/user); setup wizard; user lifecycle (deactivate/reactivate with guardrails); add/edit/delete expenses (even split only); expense feed; basic dashboard; health probes + structured logging. UX gate: add 10+ test expenses in <5 min
- **MVP1b — Settlement Flow:** 3-step settlement (review → select/deselect → settle); reference ID generation; settlement history with drill-down; settled/unsettled tabs; audit trail. UX gate: run 2-3 mock settlements
- **MVP1c — Split Modes + Expense Status (Go-Live Gate):** 4 split modes; pending/gift status lifecycle; per-expense notes; prominent date picker; dashboard recurring cost overview (read-only). Go-live gate: begin real data entry with Partner after this passes; MVP1d ships as enhancement to live system. UX gate: all split modes + gift toggle working cleanly
- **MVP1d — Recurring Cost Engine + Polish:** recurring cost registry (create/edit/delete/pause/reactivate); auto-generate + manual modes with idempotent dual-trigger; normalized monthly display; dashboard widget; keyword search; responsive polish. UX gate: 5-6 recurring costs, simulate full month end-to-end

## Scope Boundaries

| In | Out/Deferred |
|----|-------------|
| 4 split modes | OCR receipt scanning (stretch) |
| Pending/gift expense lifecycle | Multi-currency conversion (stretch) |
| 3-step settlement with reference ID | Event-level participant weights (stretch) |
| Recurring cost registry | Guest/magic link access (MVP2) |
| OIDC via Authentik + Authlib | Time-bound event groups (MVP2) |
| Group-scoped routes | Tags/categories (MVP2 events only) |
| Audit trail | Spending analytics (out of scope — personal finance tools) |
| Responsive HTML + HTMX | Offline/PWA (phone native capture is workaround) |
| Structured JSON logging | Notification/nudge system (self-interest drives participation) |
| CI/CD + ArgoCD deployment | Accessibility (not a priority for personal app) |
| MkDocs documentation | i18n (English only; Swedish as stretch) |
| | Bank API integration (security concerns) |
| | Multi-tenancy (one instance per household) |
| | Helm chart (k8s manifests + docker-compose sufficient) |
| | User-customizable tags (predefined in config) |
| | Migration from old system (clean start) |

## Decisions & Rejected Alternatives

- Rejected: separate approval step for expenses. Reason: settlement review IS the approval workflow — one combined flow
- Rejected: event-splitter model (Splitwise/Spliit). Reason: household never closes; need periodic settlement on permanent group
- Rejected: template system for recurring costs. Reason: form field simpler; registry-based engine chosen in PRD evolution
- Rejected: photo as permanent attachment. Reason: storage burden; photos are temporary OCR/capture input only
- Rejected: weekly nudge/reminder system. Reason: fights against natural incentive structure; payer logs because they want money back
- Rejected: predefined "accepted" status on expenses. Reason: simplified to binary pending/gift; no separate accepted status in MVP1
- Rejected: manual user selection dropdown on expense form. Reason: eliminated when OIDC added; identity derived from authenticated session
- Rejected: binary Authentik reverse-proxy auth (original plan). Reason: evolved to OIDC integration via Authlib for proper auto-provisioning and identity
- Rejected: SPA framework (React/Vue/Svelte). Reason: HTMX + server-rendered keeps stack simple, no Node.js runtime
- Rejected: SQLite for non-test contexts. Reason: Postgres for dev and production (same environment)
- Rejected: Helm chart. Reason: overkill; k8s manifests + docker-compose examples sufficient
- Rejected: concurrency handling. Reason: extremely unlikely at this scale; first-to-confirm wins, manual fix if needed
- Decision: `created_by` vs `paid_by` on Expense. Reason: solves "on behalf of" cleanly without a separate field
- Decision: gift status toggle (not delete). Reason: gift excludes from balance but keeps expense visible in feed and history; delete removes entirely
- Decision: deselect during settlement = UI state only. Reason: deselected expenses remain pending for future settlements without changing their status
- Decision: edit-forward semantics for recurring definitions. Reason: already-created expenses in feed remain unchanged; only future generation affected

## Resolved Design Tensions (from brainstorming)

1. Capture speed vs. data richness → "capture-first, enrich-later"; amount is the only required field
2. Simplicity vs. flexibility in splits → two-speed UI; default even; "More options" for 4-mode selector
3. Trust vs. accountability → trust + audit trail; no enforcement, complete history
4. Household vs. event differences → unified group model with lifecycle variants; household = permanent, event = time-bound
5. Template system vs. form field → form field won for MVP; evolved to registry-based engine in PRD
6. Photo as proof vs. photo as input → input won; temporary storage, no permanent burden
7. Separate approval vs. settlement review → combined; review screen IS approval workflow

## Open Questions / Unresolved Items

- Settlement calculation performance at scale (noted: 15 expenses already visible in logs; not a real problem at MVP scale)
- Currency handling for mixed-currency settlements is manual in MVP1 — no clear upgrade path defined
- Recurring cost definition: what happens to paused definitions during a settlement cycle? (implied: excluded from generation + reminders, included if manually created)
- External cron scheduling for auto-generate endpoint: no specific tooling prescribed
- DB backup and recovery strategy: documented as NFR21 prerequisite but strategy not defined in PRD

## Success Criteria

- Both partners have clear overview of all shared recurring costs — normalized monthly total visible on dashboard at a glance
- Expense capture < 30 seconds; monthly settlement < 15 minutes
- Partner adopts cost-tracker as primary tool within first month of deployment
- "Receipts in a bowl" workflow fully abandoned within first month
- Actively used for 6+ months without reverting
- Zero disputed settlements due to calculation errors
- KPIs: 20-40 expenses/month; 100% months settled; 5-8 recurring definitions active by end of month 2; zero unplanned downtime; 100% CI pass rate on merge to main
- Technical: sub-second page loads all primary views; <200ms HTMX partials; clean PR → CI → GHCR → ArgoCD sync pipeline
