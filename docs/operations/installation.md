# Installation

How to install and run Cost Tracker for the first time.

## Prerequisites

- **Docker** and **Docker Compose** — for running the application and PostgreSQL
- **An OIDC provider** — [Authentik](https://goauthentik.io/) recommended, but any
  OpenID Connect provider works
- **PostgreSQL 18+** — included via Docker Compose for local use, or use a managed instance

## Quick Start with Docker

### 1. Get the image

```bash
docker pull ghcr.io/golgor/cost-tracker:latest
```

Or build from source:

```bash
git clone https://github.com/golgor/cost-tracker.git
cd cost-tracker
docker build -t cost-tracker .
```

### 2. Start PostgreSQL

For a quick local setup, use the included Docker Compose file:

```bash
docker compose up -d
```

This starts PostgreSQL 18 on port 5433 with default credentials (`costtracker`/`costtracker`).

For production, use a dedicated PostgreSQL instance. See [Database](database.md).

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your settings. At minimum, configure:

```text
DATABASE_URL=postgresql://costtracker:costtracker@localhost:5433/costtracker
SECRET_KEY=<generate-a-random-string>
OIDC_ISSUER=https://auth.example.com/application/o/cost-tracker/
OIDC_CLIENT_ID=cost-tracker
OIDC_CLIENT_SECRET=<from-your-oidc-provider>
OIDC_REDIRECT_URI=http://localhost:8000/auth/callback
ENV=dev
```

Generate a secure secret key:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

See [Configuration Reference](configuration.md) for all available settings.

### 4. Run database migrations

```bash
docker run --env-file .env --network host ghcr.io/golgor/cost-tracker:latest \
  alembic upgrade head
```

This creates all database tables. Run this once on first setup and after each upgrade.

### 5. Start the application

```bash
docker run --env-file .env -p 8000:8000 ghcr.io/golgor/cost-tracker:latest
```

The app is now running at `http://localhost:8000`.

### 6. First login

1. Navigate to `http://localhost:8000` — you'll be redirected to your OIDC provider
2. Log in with your OIDC credentials
3. Your account is automatically provisioned from your OIDC profile
4. Your partner logs in the same way — both users are equal partners (no admin roles)

## Verify Installation

Check the health endpoints:

```bash
# Is the app running?
curl http://localhost:8000/health/live
# → {"status": "ok"}

# Is the database connected?
curl http://localhost:8000/health/ready
# → {"status": "ok", "database": "connected"}
```

## What's Next

- [Configuration](configuration.md) — All environment variables explained
- [Authentication](authentication.md) — OIDC provider setup with Authentik
- [Deployment](deployment.md) — Production deployment with GHCR and k3s
- [Database](database.md) — PostgreSQL management, migrations, and backups
