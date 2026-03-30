# Troubleshooting

Common issues and how to resolve them.

## Startup Failures

### Missing environment variables

```text
❌ Missing required environment variables:
   • DATABASE_URL
   • SECRET_KEY
```

**Fix:** Set all required variables. Copy `.env.example` as a starting point:

```bash
cp .env.example .env
```

See [Configuration](configuration.md) for the full list.

### Insecure secrets in production

```text
ValueError: SECRET_KEY must be set to a secure value in production
```

**Fix:** When `ENV=prod`, the app rejects known insecure defaults. Generate real secrets:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Set unique values for `SECRET_KEY`, `OIDC_CLIENT_SECRET`, and `INTERNAL_WEBHOOK_SECRET`.

## Database Issues

### Cannot connect to PostgreSQL

```text
psycopg2.OperationalError: could not connect to server: Connection refused
```

**Fix:**

1. Check that PostgreSQL is running: `docker ps | grep postgres`
2. Start it if needed: `docker compose up -d`
3. Verify the connection string in `DATABASE_URL`
4. For Docker Compose, the default port is **5433** (not 5432)
5. Test the connection directly: `psql "$DATABASE_URL"`

### Health check returns 503

```json
{"status": "unavailable", "database": "disconnected"}
```

**Fix:**

1. Check PostgreSQL is running and accessible
2. Run migrations if tables don't exist: `alembic upgrade head`
3. Verify `DATABASE_URL` credentials
4. Check network connectivity between the app and database

### Migration fails

```text
alembic.util.exc.CommandError: Can't locate revision identified by 'xxx'
```

**Fix:** The `alembic_version` table in the database may reference a revision that doesn't exist
in the code. Check current state with `alembic current` and compare with `alembic history`.

## Authentication Issues

### Login redirects fail or loop

**Fix:**

1. Verify `OIDC_REDIRECT_URI` matches exactly in both app config and OIDC provider
2. Local dev: `http://localhost:8000/auth/callback`
3. Production: `https://costs.example.com/auth/callback` (must be HTTPS)
4. Check that the OIDC issuer URL is reachable from the app

### "State mismatch" error

**Cause:** Stale OAuth state, usually from an expired or duplicated login attempt.

**Fix:** The app handles this automatically by clearing cookies and restarting the login flow.
If it persists, clear browser cookies manually.

### User cannot log in (new user)

**Cause:** The `MAX_USERS` limit (default 2) has been reached and the app cannot provision a
new user.

**Fix:** If the household already has two users, a third cannot be added. If a user needs to
be replaced, remove or disable them in the OIDC provider first, then adjust `MAX_USERS` if
needed.

### CSRF validation fails (403)

**Fix:**

1. Ensure cookies are enabled in the browser
2. For HTMX requests: verify `X-CSRF-Token` header is sent
3. For form submissions: verify `_csrf_token` hidden field is present
4. If `SECRET_KEY` changed, all existing CSRF tokens are invalidated — users need to reload

## Recurring Expenses

### Auto-generation not working

**Fix:**

1. Check that the cron job is running and calling the correct endpoint
2. Verify the `Authorization: Bearer <secret>` header matches `INTERNAL_WEBHOOK_SECRET`
3. Test manually:

   ```bash
   curl -v -H "Authorization: Bearer $INTERNAL_WEBHOOK_SECRET" \
     https://costs.example.com/api/internal/generate-recurring
   ```

4. Check application logs for errors during generation
5. Verify recurring definitions have `auto_generate=true` and `is_active=true`

### Duplicate billing period error

```text
DuplicateBillingPeriodError: Billing period 2026-03 already recorded
```

**Cause:** The expense for this period was already generated (by login trigger or a previous
cron run). This is expected and safe — the error is handled gracefully.

## Performance

### Slow page loads

**Fix:**

1. Check database query performance: look at `duration_ms` in logs
2. Ensure PostgreSQL has adequate resources
3. Verify indexes exist (migrations create them automatically)
4. Consider connection pooling with PgBouncer for high-traffic scenarios

## Logging

### Development (console output)

```text
[2026-03-28 15:30:45] request method=POST path=/expenses status_code=201 duration_ms=45.23
```

### Production (JSON)

```json
{"request_id": "abc-123", "method": "POST", "path": "/expenses",
 "status_code": 201, "duration_ms": 45.23, "timestamp": "2026-03-28T15:30:45Z"}
```

Log format is controlled by `ENV`:

- `dev` — colored console output (human-readable)
- `prod` — JSON lines (machine-parseable, suitable for log aggregation)

Each request gets a unique `request_id` (also returned in the `X-Request-Id` response header)
for tracing through log aggregation systems.

### Adjusting log verbosity

Set `LOG_LEVEL` in your environment:

- `DEBUG` — verbose, includes SQLAlchemy queries
- `INFO` — default, includes request logs
- `WARNING` — quieter, only warnings and errors
- `ERROR` — minimal, only errors
