from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session, text
from starlette.middleware.sessions import SessionMiddleware

from app.auth.middleware import AuthMiddleware, CSRFMiddleware
from app.dependencies import get_db_session

DbSession = Annotated[Session, Depends(get_db_session)]
from app.domain.errors import DomainError
from app.logging import RequestLoggingMiddleware, configure_logging
from app.settings import settings

# Maps DomainError subclasses → HTTP status codes.
# Add entries here as new domain errors are defined in later stories.
DOMAIN_ERROR_MAP: dict[type[DomainError], int] = {}


def create_app() -> FastAPI:
    configure_logging(env=settings.ENV, log_level=settings.LOG_LEVEL)

    app = FastAPI(title="Cost Tracker", version="0.1.0")

    # Middleware order matters: last added = first to process request
    # type: ignore[arg-type] — Starlette middleware classes are valid but FastAPI's
    # add_middleware signature is typed for BaseHTTPMiddleware subclasses only.
    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)  # type: ignore[arg-type]
    app.add_middleware(RequestLoggingMiddleware)  # type: ignore[arg-type]
    app.add_middleware(CSRFMiddleware)  # type: ignore[arg-type]
    app.add_middleware(AuthMiddleware)  # type: ignore[arg-type]

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        status_code = DOMAIN_ERROR_MAP.get(type(exc), 422)
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    @app.get("/health")
    async def health(session: DbSession) -> dict:
        """Health check endpoint - public, no auth required."""
        try:
            session.exec(text("SELECT 1"))
            db_status = "connected"
        except Exception:
            db_status = "disconnected"
        return {"status": "ok", "database": db_status}

    from app.web.router import router as web_router

    app.include_router(web_router)

    return app


app = create_app()
