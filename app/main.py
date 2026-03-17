from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlmodel import Session
from starlette.middleware.sessions import SessionMiddleware

from app.auth.middleware import AuthMiddleware, CSRFMiddleware
from app.dependencies import engine, get_db_session
from app.domain.errors import (
    DeactivatedUserAccessDenied,
    DomainError,
    DuplicateHouseholdError,
    DuplicateMembershipError,
    GroupNotFoundError,
    LastActiveAdminDeactivationForbidden,
    MembershipNotFoundError,
    UnauthorizedGroupActionError,
    UserAlreadyActive,
    UserAlreadyAdminError,
    UserAlreadyDeactivated,
    UserAlreadyRegularError,
    UserHasActiveGroupMembershipError,
    UserNotFoundError,
)
from app.logging import RequestLoggingMiddleware, configure_logging
from app.settings import settings
from app.web.router import router as web_router

DbSession = Annotated[Session, Depends(get_db_session)]

# Maps DomainError subclasses → HTTP status codes.
# Add entries here as new domain errors are defined in later stories.
DOMAIN_ERROR_MAP: dict[type[DomainError], int] = {
    DuplicateHouseholdError: 409,
    DuplicateMembershipError: 409,
    GroupNotFoundError: 404,
    MembershipNotFoundError: 404,
    UnauthorizedGroupActionError: 403,
    LastActiveAdminDeactivationForbidden: 409,
    UserHasActiveGroupMembershipError: 409,
    DeactivatedUserAccessDenied: 403,
    UserNotFoundError: 404,
    UserAlreadyAdminError: 409,
    UserAlreadyRegularError: 409,
    UserAlreadyDeactivated: 409,
    UserAlreadyActive: 409,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown logic."""
    configure_logging(env=settings.ENV, log_level=settings.LOG_LEVEL)
    yield
    engine.dispose()


app = FastAPI(title="Cost Tracker", version="0.1.0", lifespan=lifespan)

# Middleware (order matters: last added = first to process request)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)  # type: ignore[arg-type]
app.add_middleware(RequestLoggingMiddleware)  # type: ignore[arg-type]
app.add_middleware(CSRFMiddleware)  # type: ignore[arg-type]
app.add_middleware(AuthMiddleware)  # type: ignore[arg-type]

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Routers
app.include_router(web_router)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    status_code = DOMAIN_ERROR_MAP.get(type(exc), 422)
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


@app.get("/health/live")
async def liveness() -> dict:
    """Liveness probe - is the app running? Shallow check, no dependencies."""
    return {"status": "ok"}


@app.get("/health/ready", response_model=None)
async def readiness(session: DbSession) -> JSONResponse:
    """Readiness probe - can the app handle traffic? Verifies DB connectivity."""
    try:
        session.connection().execute(text("SELECT 1"))
        return JSONResponse(content={"status": "ok", "database": "connected"})
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": "disconnected"},
        )
