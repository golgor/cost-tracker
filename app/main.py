from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.domain.errors import DomainError
from app.logging import RequestLoggingMiddleware, configure_logging
from app.settings import settings

# Maps DomainError subclasses → HTTP status codes.
# Add entries here as new domain errors are defined in later stories.
DOMAIN_ERROR_MAP: dict[type[DomainError], int] = {}


def create_app() -> FastAPI:
    configure_logging(env=settings.ENV, log_level=settings.LOG_LEVEL)

    app = FastAPI(title="Cost Tracker", version="0.1.0")

    # type: ignore[arg-type] — Starlette middleware classes are valid but FastAPI's
    # add_middleware signature is typed for BaseHTTPMiddleware subclasses only.
    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)  # type: ignore[arg-type]
    app.add_middleware(RequestLoggingMiddleware)  # type: ignore[arg-type]

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        status_code = DOMAIN_ERROR_MAP.get(type(exc), 422)
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    @app.get("/health")
    async def health() -> dict:
        db_status = _check_db()
        return {"status": "ok", "database": db_status}

    from app.web.router import router as web_router

    app.include_router(web_router)

    return app


# App-level engine for health checks (avoids creating engine per request)
_health_check_engine = None


def _get_health_check_engine():
    """Lazily create and cache a lightweight engine for health checks."""
    global _health_check_engine
    if _health_check_engine is None:
        from sqlalchemy import create_engine

        _health_check_engine = create_engine(
            settings.DATABASE_URL, pool_pre_ping=True, pool_size=1, max_overflow=0
        )
    return _health_check_engine


def _check_db() -> str:
    """Return 'connected' or 'disconnected' based on a lightweight DB ping."""
    try:
        from sqlalchemy import text

        engine = _get_health_check_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "connected"
    except Exception:
        return "disconnected"


app = create_app()
