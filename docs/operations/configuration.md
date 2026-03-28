# Configuration Reference

Cost Tracker is configured through environment variables. Use a `.env` file for local development
or set variables directly in your deployment environment.

A `.env.example` template is included in the repository.

## Required Variables

These must be set for the application to start.

### `DATABASE_URL`

PostgreSQL connection string.

```text
DATABASE_URL=postgresql://user:password@localhost:5433/cost_tracker
```

### `SECRET_KEY`

Secret key for signing session cookies. Must be a long, random string.

```text
SECRET_KEY=your-random-secret-key-here
```

In production, the app will refuse to start if this is set to a known insecure default.

### `OIDC_ISSUER`

Base URL of your OpenID Connect provider (e.g., Authentik).

```text
OIDC_ISSUER=https://auth.example.com/application/o/cost-tracker/
```

### `OIDC_CLIENT_ID`

OAuth2 client ID from your OIDC provider.

```text
OIDC_CLIENT_ID=cost-tracker
```

### `OIDC_CLIENT_SECRET`

OAuth2 client secret from your OIDC provider.

```text
OIDC_CLIENT_SECRET=your-client-secret
```

In production, the app will refuse to start if this is set to a known insecure default.

### `OIDC_REDIRECT_URI`

OAuth2 callback URL. Must match the redirect URI configured in your OIDC provider.

```text
OIDC_REDIRECT_URI=https://costs.example.com/callback
```

## Optional Variables

These have sensible defaults and can be omitted.

### `SESSION_MAX_AGE`

Session cookie lifetime in seconds.

- **Default:** `86400` (24 hours)
- **Example:** `SESSION_MAX_AGE=604800` (7 days)

### `LOG_LEVEL`

Application log level. Uses Python's standard logging levels.

- **Default:** `INFO`
- **Values:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

### `ENV`

Environment mode. Controls security validation behavior.

- **Default:** `dev`
- **Values:** `dev`, `prod`

When set to `prod`, the application validates that `SECRET_KEY`, `OIDC_CLIENT_SECRET`, and
`INTERNAL_WEBHOOK_SECRET` are not set to known insecure defaults.

### `INTERNAL_WEBHOOK_SECRET`

Secret for signing internal webhook requests.

- **Default:** `change-me-webhook-secret` (insecure — must be changed in production)

### `SYSTEM_ACTOR_ID`

User ID used for automated system-initiated actions in the audit log.

- **Default:** `0`

## Production Checklist

When deploying to production (`ENV=prod`), ensure:

- [ ] `SECRET_KEY` is set to a cryptographically random value
- [ ] `OIDC_CLIENT_SECRET` is set to the real secret from your OIDC provider
- [ ] `INTERNAL_WEBHOOK_SECRET` is set to a unique, random value
- [ ] `DATABASE_URL` points to your production PostgreSQL instance
- [ ] `OIDC_REDIRECT_URI` uses your production domain with HTTPS

## Loading Configuration

Settings are loaded via [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
from environment variables or a `.env` file. The `.env` file is read automatically if present in
the project root.

If required variables are missing, the application exits with a clear error message listing the
missing fields.
