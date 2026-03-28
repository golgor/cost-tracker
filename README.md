# Cost Tracker

Self-hosted household expense-sharing app for partners. Track shared expenses, calculate balances,
and settle up monthly.

Built with FastAPI, PostgreSQL, HTMX, and Tailwind CSS. Designed for simplicity — log expenses as
they happen, review together, settle via bank transfer, repeat.

## Features

- **Expense tracking** with flexible splits (even, percentage, shares, exact)
- **Real-time balance** showing who owes whom
- **Monthly settlements** with co-located review flow
- **Recurring costs** (rent, subscriptions) with auto-generation
- **Full audit trail** for transparency
- **Mobile-first capture** with desktop batch entry support
- **OIDC authentication** (Authentik or any OpenID Connect provider)

## Quick Start

### Prerequisites

- Docker and Docker Compose
- An OIDC provider (e.g., [Authentik](https://goauthentik.io/))

### Run with Docker Compose

```bash
# Start PostgreSQL
docker compose up -d

# Copy and configure environment
cp .env.example .env
# Edit .env with your database URL, OIDC settings, and secret key

# Build and run
docker build -t cost-tracker .
docker run --env-file .env -p 8000:8000 cost-tracker
```

See the [Operations Guide](docs/operations/index.md) for full deployment instructions.

## Development

```bash
# Install dependencies
uv sync

# Start PostgreSQL
mise run db

# Run migrations
mise run migrate

# Start dev server (uvicorn + Tailwind watcher)
mise run dev
```

Requires Python 3.14, [uv](https://docs.astral.sh/uv/), and
[mise](https://mise.jdx.dev/).

See the [Development Guide](docs/development/index.md) for full setup instructions.

## Documentation

Full documentation lives in [`docs/`](docs/index.md) and is built with
[MkDocs Material](https://squidfunk.github.io/mkdocs-material/).

| Section | Audience | Content |
| --- | --- | --- |
| [User Guide](docs/user-guide/index.md) | End users, evaluators | What it does, how to use it |
| [Operations](docs/operations/index.md) | Self-hosters | Install, configure, deploy, maintain |
| [Development](docs/development/index.md) | Contributors | Setup, conventions, testing |
| [Architecture](docs/architecture/index.md) | Developers | ADRs, patterns, boundaries |
| [Design Records](docs/design/index.md) | Reference | Archived UX and architecture design artifacts |

## Tech Stack

| Component | Technology |
| --- | --- |
| Backend | FastAPI (Python 3.14) |
| Database | PostgreSQL 18 |
| ORM | SQLModel + SQLAlchemy |
| Frontend | Jinja2 + HTMX + Tailwind CSS |
| Auth | OIDC (Authentik) via Authlib |
| Package manager | uv (Astral) |
| Task runner | mise |
| Deployment | Docker, GHCR, ArgoCD, k3s |

## Architecture

Hexagonal architecture (ports & adapters) with a pure Python domain layer. See
[Architecture docs](docs/architecture/index.md) for details.

```text
app/
├── domain/      # Pure business logic, no framework imports
├── adapters/    # SQLAlchemy implementations of domain ports
├── auth/        # OIDC, sessions, CSRF
├── web/         # Routes, templates, forms
└── main.py      # App factory and middleware
```

## License

See [LICENSE](LICENSE).
