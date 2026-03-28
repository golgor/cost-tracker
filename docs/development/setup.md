# Local Setup

How to set up a local development environment for Cost Tracker.

## Prerequisites

- **Python 3.14** — required runtime version
- **[uv](https://docs.astral.sh/uv/)** — Python package manager (replaces pip)
- **[mise](https://mise.jdx.dev/)** — task runner and tool version manager
- **Docker** and **Docker Compose** — for PostgreSQL

mise manages Python, uv, and markdownlint-cli2 versions automatically via `mise.toml`.

## First-Time Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/golgor/cost-tracker.git
cd cost-tracker
uv sync
```

`uv sync` installs all dependencies from the lockfile (`uv.lock`) into a local `.venv`.

### 2. Start PostgreSQL

```bash
mise run db
```

This runs `docker-compose up -d`, starting PostgreSQL 18 on port **5433** (not the default 5432,
to avoid conflicts with any system PostgreSQL).

Default credentials:

| Setting | Value |
| --- | --- |
| Host | `localhost` |
| Port | `5433` |
| Database | `costtracker` |
| User | `costtracker` |
| Password | `costtracker` |

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your local settings. The defaults in `.env.example` work for the Docker Compose
PostgreSQL setup. For OIDC, you need a running Authentik instance (or another OIDC provider).

Key variables for local development:

```text
DATABASE_URL=postgresql://costtracker:costtracker@localhost:5433/costtracker
SECRET_KEY=change-me-in-production
OIDC_ISSUER=https://auth.example.com/application/o/cost-tracker/
OIDC_CLIENT_ID=cost-tracker
OIDC_CLIENT_SECRET=change-me
OIDC_REDIRECT_URI=http://localhost:8000/auth/callback
ENV=dev
```

See [Configuration Reference](../operations/configuration.md) for all available settings.

### 4. Run database migrations

```bash
mise run migrate
```

This runs `alembic upgrade head` to create all database tables.

### 5. Start the development server

You need **two terminals**:

**Terminal 1** — FastAPI server with auto-reload:

```bash
mise run dev
```

**Terminal 2** — Tailwind CSS watcher (compiles CSS on file changes):

```bash
mise run dev:css
```

The app is now running at `http://localhost:8000`.

## Common Tasks

| Command | What it does |
| --- | --- |
| `mise run dev` | Start FastAPI dev server with reload |
| `mise run dev:css` | Watch and compile Tailwind CSS |
| `mise run test` | Run all tests (requires PostgreSQL) |
| `mise run test:unit` | Run unit tests only |
| `mise run test:integration` | Run integration tests |
| `mise run lint` | Check code style (ruff) and types (ty) |
| `mise run lint:fix` | Auto-fix code style and formatting |
| `mise run lint:docs` | Lint markdown documentation |
| `mise run migrate` | Run pending Alembic migrations |
| `mise run db` | Start PostgreSQL container |
| `mise run types` | Fast type checking only (~1s) |

## Code Style

Enforced by [ruff](https://docs.astral.sh/ruff/):

- **Line length:** 100 characters
- **Quote style:** double quotes
- **Indent style:** spaces
- **Import sorting:** isort-compatible, `app` as first-party
- **Rules:** E, F, I, UP, B, SIM (pyflakes, pycodestyle, isort, pyupgrade, bugbear,
  flake8-simplicity)

Type checking uses [ty](https://github.com/astral-sh/ty) with Python 3.14 target.

Always run `mise run lint:fix` before committing to auto-format.

## Test Database

Tests use a separate PostgreSQL database with a `_test` suffix. It is auto-created from
`DATABASE_URL` when you first run tests:

- `DATABASE_URL=postgresql://...costtracker` → test DB: `costtracker_test`

You can also set `TEST_DATABASE_URL` explicitly (used in CI). Each test runs in a transaction
that is rolled back automatically, so tests don't leave data behind.

See [Testing](testing.md) for the full testing guide.

## Project Structure

```text
app/
├── domain/          # Pure business logic (no framework imports)
│   ├── models.py    # SQLModel base + public classes
│   ├── ports.py     # Protocol interfaces for adapters
│   ├── errors.py    # Domain exception hierarchy
│   └── use_cases/   # Business operations
├── adapters/        # SQLAlchemy implementations
│   └── sqlalchemy/
│       ├── orm_models.py    # XxxRow table classes
│       ├── *_adapter.py     # Port implementations
│       ├── unit_of_work.py  # Transaction management
│       └── queries/         # Read-only view queries
├── auth/            # OIDC, sessions, CSRF
├── web/             # Routes, templates, forms
├── dependencies.py  # Composition root (wiring)
├── main.py          # App factory, middleware
├── settings.py      # Environment config
└── logging.py       # structlog setup
```

For architecture details, see [Architecture](../architecture/index.md).
For naming conventions, see [Conventions](conventions.md).
