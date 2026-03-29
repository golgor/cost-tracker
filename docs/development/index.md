# Development

Guides for contributing to and maintaining Cost Tracker.

## Getting Started

- [Local Setup](setup.md) — Dev environment with uv, mise, and PostgreSQL
- [Conventions](conventions.md) — Naming, patterns, and mandatory rules
- [Testing](testing.md) — Test strategy, running tests, and writing new tests

## How-To Guides

- [Add a Domain Entity](how-to/add-domain-entity.md) — New model, port, adapter, and route
- [Add a Route](how-to/add-route.md) — New page or HTMX endpoint
- [Add a Migration](how-to/add-migration.md) — Alembic database migrations

## Integrations

- [Glance Dashboard](glance-integration.md) — Read-only JSON API for Glance `custom-api` widgets

## Architecture

For deeper understanding of design decisions and patterns, see the
[Architecture](../architecture/index.md) section.

## AI Agent Configuration

This project uses Claude sub-agents for development assistance. Agent configuration lives in
`CLAUDE.md` and `AGENTS.md` at the project root — these are the authoritative source for AI-specific
conventions and are not duplicated here.
