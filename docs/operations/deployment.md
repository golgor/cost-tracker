# Deployment

Cost Tracker is deployed as a single Docker image. No Node.js or build tools are needed at
runtime — Tailwind CSS is pre-compiled during the Docker build.

## Docker Image

### Pre-built Image

Images are published to GitHub Container Registry on every push to `main`:

```bash
docker pull ghcr.io/golgor/cost-tracker:latest
```

Tags:

- `latest` — most recent `main` build
- `sha-<commit>` — specific commit

### Build from Source

```bash
docker build -t cost-tracker .
```

The Dockerfile uses a multi-stage build:

1. **Builder stage** (`ghcr.io/astral-sh/uv:python3.14-bookworm-slim`)
   - Installs Python dependencies from lockfile
   - Downloads Tailwind CSS v4 standalone binary (architecture-aware: amd64/arm64)
   - Compiles and minifies CSS
2. **Production stage** (`python:3.14-slim-bookworm`)
   - Copies pre-built virtualenv and compiled CSS
   - Runs uvicorn on port 8000

## Deployment Options

### Docker on a VPS

The simplest production deployment:

```bash
docker pull ghcr.io/golgor/cost-tracker:latest

docker run -d \
  --name cost-tracker \
  --env-file .env.prod \
  -p 8000:8000 \
  --restart unless-stopped \
  ghcr.io/golgor/cost-tracker:latest
```

Place behind a reverse proxy (e.g., [Traefik](https://traefik.io/)) for HTTPS termination.

### k3s with ArgoCD

The project's reference deployment uses:

- **GHCR** — container registry (images pushed by CI)
- **ArgoCD** — GitOps-based deployment
- **k3s** — lightweight Kubernetes
- **PostgreSQL** — on a separate Proxmox VM (not in the cluster)

Deployment flow:

```text
git push → GitHub Actions → build + push to GHCR → ArgoCD detects → k3s rolls out
```

No Kubernetes manifests are included in this repository — create them for your cluster.

A minimal deployment needs:

- Deployment with 1 replica
- Service (ClusterIP) on port 8000
- Ingress for HTTPS
- Secret for environment variables
- ConfigMap for non-sensitive settings

### Health Probes

Configure container health probes:

| Probe | Endpoint | Purpose | Suggested Interval |
| --- | --- | --- | --- |
| Liveness | `GET /health/live` | Is the process running? | 30s |
| Readiness | `GET /health/ready` | Is the database connected? | 10s |

The readiness probe runs `SELECT 1` against PostgreSQL. If it fails, the app returns 503 and
should be removed from the load balancer until the database recovers.

## Running Migrations

Migrations must be run **before** starting the new version. In a Kubernetes context, use an
init container or a pre-deploy job:

```bash
docker run --rm --env-file .env.prod \
  ghcr.io/golgor/cost-tracker:latest \
  alembic upgrade head
```

See [Database](database.md) for migration details.

## Recurring Expense Auto-Generation

Cost Tracker can auto-generate expenses from recurring definitions. This is triggered by:

1. **On login** — best-effort, non-blocking (runs automatically)
2. **External cron job** — recommended for reliability

Set up a cron job to call the internal webhook:

```bash
# Daily at 2:00 AM
0 2 * * * curl -sf -H "Authorization: Bearer $INTERNAL_WEBHOOK_SECRET" \
  https://costs.example.com/api/internal/generate-recurring
```

The `INTERNAL_WEBHOOK_SECRET` must match the value in your environment configuration.

## Reverse Proxy

The app runs on port 8000 and expects a reverse proxy for HTTPS. [Traefik](https://traefik.io/)
is recommended — it handles automatic HTTPS via Let's Encrypt and integrates natively with Docker
and Kubernetes.

### Traefik with Docker labels

Add labels to your Cost Tracker container to let Traefik auto-discover it:

```yaml
services:
  cost-tracker:
    image: ghcr.io/golgor/cost-tracker:latest
    env_file: .env.prod
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.costtracker.rule=Host(`costs.example.com`)"
      - "traefik.http.routers.costtracker.entrypoints=websecure"
      - "traefik.http.routers.costtracker.tls.certresolver=letsencrypt"
      - "traefik.http.services.costtracker.loadbalancer.server.port=8000"
```

### Traefik with Kubernetes IngressRoute

For k3s deployments (Traefik is the default ingress controller in k3s):

```yaml
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: cost-tracker
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`costs.example.com`)
      kind: Rule
      services:
        - name: cost-tracker
          port: 8000
  tls:
    certResolver: letsencrypt
```

## CI/CD Pipeline

GitHub Actions workflows run automatically:

| Workflow | Trigger | What it does |
| --- | --- | --- |
| `code.yml` | Changes to `app/`, `tests/` | Lint, type check, unit + integration tests |
| `docker.yml` | Changes to `Dockerfile`, `app/` | Build image, push to GHCR |
| `docs.yml` | Changes to `docs/`, `mkdocs.yml` | Markdown lint, MkDocs build |

Images are only pushed on merges to `main` (not on PRs).

## Production Checklist

- [ ] PostgreSQL 18+ running and accessible
- [ ] All required env vars set (see [Configuration](configuration.md))
- [ ] `ENV=prod` to enable security validation
- [ ] `SECRET_KEY` is a unique random value
- [ ] `OIDC_CLIENT_SECRET` is the real secret from your provider
- [ ] `INTERNAL_WEBHOOK_SECRET` is a unique random value
- [ ] HTTPS configured via reverse proxy
- [ ] `OIDC_REDIRECT_URI` uses your production domain with HTTPS
- [ ] Database migrations run: `alembic upgrade head`
- [ ] Health probes configured in orchestrator
- [ ] Cron job set up for recurring expense generation
- [ ] Backup strategy for PostgreSQL (see [Database](database.md))
