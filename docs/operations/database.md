# Database

Cost Tracker uses PostgreSQL 18+ as its only database. All data — users, expenses, settlements,
audit logs — lives in a single PostgreSQL instance.

## Local Development

The included Docker Compose file runs PostgreSQL for development:

```bash
mise run db
# or: docker compose up -d
```

Default connection details:

| Setting | Value |
| --- | --- |
| Host | `localhost` |
| Port | `5433` (non-standard to avoid conflicts) |
| Database | `costtracker` |
| User | `costtracker` |
| Password | `costtracker` |

Connection string: `postgresql://costtracker:costtracker@localhost:5433/costtracker`

Data is persisted in a Docker volume (`postgres_data`).

## Production Setup

For production, use a dedicated PostgreSQL instance:

- Managed service (AWS RDS, DigitalOcean, etc.) or self-hosted
- PostgreSQL 18+ recommended
- Ensure the application can reach the database (network/firewall)
- Use strong credentials and restrict access

Set the connection string via `DATABASE_URL`:

```text
DATABASE_URL=postgresql://user:password@db.example.com:5432/costtracker
```

## Migrations

Database schema is managed by [Alembic](https://alembic.sqlalchemy.org/). Migrations are
versioned with sequential numeric IDs (001, 002, ...).

### Run pending migrations

```bash
# Local development
mise run migrate

# Production (Docker)
docker run --rm --env-file .env.prod \
  ghcr.io/golgor/cost-tracker:latest \
  alembic upgrade head
```

Always run migrations **before** starting a new version of the application.

### Check current version

```bash
uv run alembic current
```

### View migration history

```bash
uv run alembic history
```

### Rollback

```bash
# Rollback last migration
uv run alembic downgrade -1

# Rollback to a specific version
uv run alembic downgrade 007
```

### Create a new migration

After modifying ORM models:

```bash
uv run alembic revision --autogenerate -m "description of change"
```

Always review the generated migration before applying it.
See [Add a Migration](../development/how-to/add-migration.md) for details.

## Backups

### pg_dump

The simplest backup approach:

```bash
# Full backup
pg_dump -h db.example.com -U costtracker -d costtracker -F custom -f backup.dump

# Restore
pg_restore -h db.example.com -U costtracker -d costtracker -c backup.dump
```

### Automated backups

Set up a cron job for regular backups:

```bash
# Daily at 3 AM, keep 30 days
0 3 * * * pg_dump -h db.example.com -U costtracker -d costtracker -F custom \
  -f /backups/costtracker_$(date +\%Y\%m\%d).dump \
  && find /backups -name "costtracker_*.dump" -mtime +30 -delete
```

### What to back up

- The PostgreSQL database contains all application data
- No file-based state outside the database (sessions are in cookies, CSS is compiled at build time)
- Back up environment files (`.env`) separately — they contain secrets

## Connection Pooling

SQLAlchemy manages connection pooling automatically. The app uses `pool_pre_ping=True` to validate
connections before use, handling cases where the database restarts.

For high-traffic deployments, consider placing [PgBouncer](https://www.pgbouncer.org/) between the
app and PostgreSQL.

## Test Database

Tests use a separate database with a `_test` suffix, auto-created on first test run:

- `costtracker` → `costtracker_test`

Override with `TEST_DATABASE_URL` if needed (e.g., in CI).

See [Testing](../development/testing.md) for details.

## Schema Overview

Core tables:

| Table | Purpose |
| --- | --- |
| `users` | User accounts (synced from OIDC) |
| `expenses` | Shared expenses |
| `expense_splits` | How expenses are divided |
| `expense_notes` | Comments on expenses |
| `settlements` | Settled payment records |
| `settlement_expenses` | Expenses included in a settlement |
| `settlement_transactions` | Individual payments within settlements |
| `recurring_definitions` | Templates for recurring costs |

All tables use `DateTime(timezone=True)` for timestamps and `Numeric(19,2)` for money values.
