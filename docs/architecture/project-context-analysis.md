# Project Context Analysis

## Requirements Overview

**Functional Requirements:**
46 FRs organized into 7 categories:

- **Expense Management** (FR1-FR8, FR46): CRUD operations, status lifecycle (proposed/accepted/gift), per-expense notes,
  currency labels, settled expense immutability
- **Split & Balance** (FR9-FR12): 4 split modes (even/shares/percentage/amount), on-demand balance calculation,
  deterministic rounding, split validation
- **Settlement** (FR13-FR22): 3-step flow (review/approve/confirm), reference ID generation (SET-{year}-{month}-{hash}),
  settlement history with drill-down, concurrent settlement protection, stateless review model
- **Recurring Costs** (FR23-FR29): Registry-based definitions with 8+ fields, auto-generate and manual modes, idempotent
  dual-trigger generation, normalized monthly cost, edit-forward semantics
- **Dashboard & Overview** (FR30-FR38): Balance summary, expense feed with tabs, recurring cost widget, settlement
  history summary, keyword search, contextual empty states
- **Group & User Management** (FR39-FR42): OIDC auto-provisioning, setup wizard, co-admin model, creator vs. payer
  distinction
- **Audit & History** (FR43-FR44): Complete audit trail for state-changing actions, expense/settlement traceability

**Non-Functional Requirements:**

- **Performance**: Page loads <1s, HTMX partials <200ms, balance calculation <500ms for ~50 expenses
- **Data Integrity**: DB-level immutability for settled expenses, split sums always exact, deterministic rounding, full
  audit trail
- **Security**: OIDC via Authentik + Authlib, signed cookie sessions, Pydantic input validation, ORM-only (no raw SQL),
  TLS at infrastructure level
- **Reliability**: Stateless app with persistent DB, backwards-compatible migrations, graceful shutdown, HTMX error
  handling
- **Observability**: Structured JSON logs with request context, health check endpoint, audit trail
- **Testing**: PostgreSQL for all tests with `_test` database suffix (auto-derived from `DATABASE_URL`).
  Test database auto-created if needed

**Scale & Complexity:**

- Primary domain: Full-stack server-rendered web application (MPA + HTMX)
- Complexity level: Medium
- Estimated architectural components: ~12-15 (models, services, route layers, templates, auth, audit, recurring engine)

## Technical Constraints & Dependencies

- **Stack**: FastAPI, PostgreSQL, Jinja2, HTMX, Tailwind CSS (all decided in PRD)
- **Auth**: OIDC with Authentik (IdP) + Authlib (client) + signed cookie session (user ID only, no token storage)
- **Deployment**: Single Docker image → GHCR → ArgoCD → k3s. Tailwind CLI runs at build time, no Node.js at runtime
- **Static assets**: HTMX and Tailwind CSS vendored — fully self-contained, no CDN
- **Testing**: pytest + ruff + ty + markdownlint-cli2 in GitHub Actions CI
- **Database**: PostgreSQL with ORM (no raw SQL per NFR19). All tests use PostgreSQL with `_test` database suffix
- **Browser**: Modern Chrome only — no polyfills, no legacy support

## Cross-Cutting Concerns Identified

1. **Authentication & Session** — Two auth paths: browser (OIDC → signed cookie with user ID + issued_at, no token
   storage) and API (API key or Bearer token for CLI/external clients). OIDC flow is login-time only; cookie expiry
   triggers transparent re-auth via Authentik redirect. CSRF tokens required on browser-facing mutations only (not API)
2. **Three-Layer Route Pattern** — Page + HTMX share URL paths (HX-Request header detection via centralized middleware).
   API gets separate `/api/v1/` prefix. Two URL namespaces, not three
3. **Audit Trail** — Single `audit_log` table with JSON diff columns (entity_type, entity_id, action, actor_id,
   timestamp, old_values_json, new_values_json). Append-only. Automatic capture via use-case-level calls within
   UnitOfWork transactions — not manual calls per route
4. **Use Case Enforcement** — Structurally necessary because three route layers exist. Use cases are the single source
   of truth for business logic. Routes are thin: validate input, call use case, render response
5. **Input Validation** — Shared Pydantic models for input validation across API and HTMX form routes. Response models
   diverge: API uses Pydantic response models (JSON), HTMX uses template context dicts (Jinja2). Three-layer defense:
   route validation (format) → use case validation (business rules) → DB constraints (safety net)
6. **HTMX Interaction Pattern** — Uniform loading states, error handling, and swap transitions. 150ms opacity fade
   baseline. Expired session on HTMX requests returns `HX-Redirect` header. `hx-disabled-elt` prevents double submission
7. **Money Precision** — `Decimal` type end to end: Pydantic models, use cases, PostgreSQL `NUMERIC` columns. Zero
   floats in the money path

## Architectural Principles (from First Principles Analysis)

1. **The expense log is the single source of truth for balance** — Balance is always derived via query, never stored,
   cached, or materialized. No balance columns, no materialized views. With ~20-40 unsettled expenses, a SUM query is
   microseconds
2. **The use case layer exists because three route layers exist** — It's structurally necessary, not optional good
   practice. If only one route layer existed, use cases would be over-engineering
3. **Input validation is shared, responses diverge by layer** — Web form models (`web/forms/`) parse and validate input
   from both API JSON and HTMX form data. API responses use separate Pydantic response models. HTMX/page responses use
   template context dicts. Endpoint structure differs: API is resource-oriented CRUD, HTMX is view-oriented fragments
4. **One audit log table with JSON diffs** — Append-only, covers all entity types. Automatic capture, not manual
   per-operation calls
5. **Two URL namespaces** — Page + HTMX share paths (header detection via centralized middleware). API gets `/api/v1/`
   prefix
6. **Thin ORM** — Simple mapped classes and explicit queries. No deep relationship graphs, no lazy loading. The domain
   is ~5 tables; keep the data access layer proportional

## Critical Failure Modes Identified

**Settlement Calculation:**

- Concurrent settlement must use `SELECT FOR UPDATE` within a transaction. Application-level checks alone are
  insufficient
- Confirm POST re-validates all selected expense IDs are still unsettled. Settles exactly the reviewed set — no attempt
  to detect additions since review
- Deterministic rounding tested with adversarial split combinations (mixed modes in one settlement)

**OIDC Authentication:**

- App cookie contains user ID + `issued_at` only. No tokens stored. Generous TTL (e.g., 7 days)
- Cookie expiry triggers redirect to Authentik, which auto-resolves via its own session (no login prompt). Two
  redirects, transparent
- HTMX requests hitting expired session get `HX-Redirect` header, not HTML error fragment
- Only Authentik's own session expiry causes an actual login prompt (configurable in Authentik, weeks)
- Signing secret from Kubernetes secret, not baked into image. Document rotation procedure

**Security:**

- CSRF tokens on all browser-facing state-changing requests (HTMX + form POST). Not needed for API (uses separate auth,
  not cookies)
- `Decimal` for all monetary values — Pydantic, use cases, PostgreSQL `NUMERIC`. Zero floats
- Three-layer validation: route (format) → use case (business rules) → DB (constraints)

**Recurring Cost Engine:**

- Idempotency via DB-level unique constraint on (definition_id, billing_period) — not application logic only. Prevents
  race conditions between dashboard trigger and internal cron
- Auto-generation is a use case function triggered on dashboard load (session-authenticated). Optionally callable by
  internal Kubernetes CronJob. Never exposed as a public endpoint
- Dashboard load should not block on generation — consider async or throttled execution to preserve <1s page load NFR

**Route Architecture:**

- HX-Request header detection must be centralized (middleware/dependency injection), not checked per-route
- Service layer is the only code that touches the DB — architectural test or lint rule to enforce this
- HTMX partial errors must swap into designated error targets, not content areas. Global `hx-on::response-error` handler
