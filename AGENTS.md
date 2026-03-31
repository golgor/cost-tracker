# Cost Tracker

Self-hosted household expense-sharing app for two partners. FastAPI + PostgreSQL + Jinja2 + HTMX + Tailwind CSS. Python 3.14, uv for package management. Hexagonal architecture (ports & adapters) — domain is pure Python, no framework imports.

No group abstraction — single household, two equal partners. Settings (currency, split type, threshold) via environment variables. User limit enforced at OIDC login via `MAX_USERS` (default 2).

## How to Work

1. **Plan first** — Enter plan mode for any 3+ step task. If something goes wrong, STOP and re-plan immediately.
2. **Use sub-agents** — Offload research, exploration, and parallel work to keep the main context clean. One task per agent.
3. **Learn from corrections** — After any user correction, update `tasks/lessons.md` with the pattern. Review it at session start.
4. **Verify before done** — Never mark complete without proving it works. Run tests, check logs, demonstrate correctness.
5. **Demand elegance** — For non-trivial changes, ask "is there a more elegant solution?" Skip for simple fixes.
6. **Fix bugs autonomously** — Given a bug report, just fix it. Use logs, errors, and failing tests to diagnose. Zero context switching for the user.
7. **Simplicity first** — Make every change as simple as possible. Find root causes — no temporary fixes.

## Commands

```bash
# Development
mise run dev              # Start dev server with reload
mise run db               # Start PostgreSQL container
mise run migrate          # Run Alembic migrations

# Testing (requires PostgreSQL)
mise run test             # Run all tests
uv run pytest tests/domain/expenses_test.py -v                        # Single file
uv run pytest tests/domain/expenses_test.py::test_create_expense -v   # Single test

# Linting
mise run lint             # ruff check + ruff format --check + ty
mise run lint:fix         # Auto-fix (always run this first)
mise run lint:docs        # Lint markdown in docs/

# Type-checking
mise run types            # Run type-checks with `ty`

# Dependencies
uv add <package>          # Add dependency (never use pip)
uv sync --locked          # Install from lockfile
```

## Code Style

- **Line length**: 120 characters
- **Quotes**: Double quotes for strings
- **Indentation**: 4 spaces
- **Python version**: 3.14+
- Import order: stdlib, third-party, first-party (`from app import ...`). Managed by ruff.

## Sub-Agents

Use the project sub-agents (`.claude/agents/`) to delegate specialized work instead of doing everything in the main conversation.

**Knowledge oracles** — delegate questions to avoid loading full docs into context:
- `architecture-lead` — architecture decisions, patterns, boundaries, naming. Ask instead of reading `docs/architecture/` yourself
- `ux-lead` — UX decisions, component behavior, user flows, visual design. Ask instead of reading `docs/ux-design/` yourself

**Workflow agents** — delegate after implementation work:
- `pr-reviewer` — review code changes against architecture rules and lessons before committing
- `tester` — run tests, check architecture enforcement, identify missing coverage
- `tech-writer` — create or update documentation in `docs/`
- `docs-linter` — run markdownlint on `docs/` and auto-fix violations. Use after editing docs or before committing

## Reference

Detailed docs — read on demand, don't load into context:
- Architecture & boundaries: `docs/architecture/`
- Naming & conventions: `docs/development/conventions.md`
- Testing patterns: `docs/development/testing.md`
- Setup & environment: `docs/development/setup.md`
- Deployment & operations: `docs/operations/`
- Lessons learned: `tasks/lessons.md`
- Planning artifacts: `_bmad-output/planning-artifacts/`
