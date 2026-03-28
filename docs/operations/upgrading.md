# Upgrading

How to upgrade Cost Tracker to a new version.

## Upgrade Process

### 1. Pull the new image

```bash
docker pull ghcr.io/golgor/cost-tracker:latest
```

Or pull a specific version:

```bash
docker pull ghcr.io/golgor/cost-tracker:sha-<commit>
```

### 2. Run database migrations

Before starting the new version, apply any new migrations:

```bash
docker run --rm --env-file .env.prod \
  ghcr.io/golgor/cost-tracker:latest \
  alembic upgrade head
```

Check what migrations will run:

```bash
docker run --rm --env-file .env.prod \
  ghcr.io/golgor/cost-tracker:latest \
  alembic current
```

### 3. Restart the application

```bash
# Docker
docker stop cost-tracker
docker rm cost-tracker
docker run -d --name cost-tracker --env-file .env.prod \
  -p 8000:8000 --restart unless-stopped \
  ghcr.io/golgor/cost-tracker:latest
```

For Kubernetes/k3s, ArgoCD handles this automatically when it detects the new image.

### 4. Verify

```bash
# Check health
curl https://costs.example.com/health/ready
# → {"status": "ok", "database": "connected"}
```

## Rollback

If something goes wrong:

### 1. Stop the new version

```bash
docker stop cost-tracker
```

### 2. Rollback the database migration (if needed)

```bash
docker run --rm --env-file .env.prod \
  ghcr.io/golgor/cost-tracker:<previous-version> \
  alembic downgrade -1
```

### 3. Start the previous version

```bash
docker run -d --name cost-tracker --env-file .env.prod \
  -p 8000:8000 --restart unless-stopped \
  ghcr.io/golgor/cost-tracker:<previous-version>
```

## Pre-Upgrade Checklist

- [ ] Back up the database: `pg_dump -F custom -f backup.dump` (see [Database](database.md))
- [ ] Check the changelog for breaking changes or new required environment variables
- [ ] Test the upgrade in a staging environment if possible
- [ ] Run migrations before starting the new version
- [ ] Verify health endpoints after restart

## Notes

- Migrations are forward-compatible — they include both `upgrade()` and `downgrade()` functions
- The application validates environment variables on startup — if a new required variable is
  missing, the app will fail to start with a clear error message
- Session cookies signed with the old `SECRET_KEY` remain valid across upgrades (unless you
  rotate the key)
