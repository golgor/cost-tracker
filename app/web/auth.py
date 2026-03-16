import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.auth.oidc import get_oauth
from app.auth.session import encode_session
from app.dependencies import get_uow
from app.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")

UowDep = Annotated[UnitOfWork, Depends(get_uow)]

_ERROR_CONTEXT = {"csrf_token": ""}


@router.get("/login")
async def login(request: Request):
    """Redirect to Authentik OIDC login."""
    oauth = get_oauth()
    redirect_uri = settings.OIDC_REDIRECT_URI

    try:
        return await oauth.authentik.authorize_redirect(request, redirect_uri)
    except Exception:
        return templates.TemplateResponse(
            request,
            "auth/error.html",
            _ERROR_CONTEXT,
            status_code=503,
        )


@router.get("/callback")
async def callback(request: Request, uow: UowDep):
    """Handle OIDC callback, provision user if needed, create session."""
    oauth = get_oauth()

    try:
        token = await oauth.authentik.authorize_access_token(request)
    except Exception as e:
        logger.error("OIDC callback failed: %s", e, exc_info=True)
        return templates.TemplateResponse(
            request,
            "auth/error.html",
            _ERROR_CONTEXT,
            status_code=400,
        )

    # Extract user info from ID token
    userinfo = token.get("userinfo", {})
    oidc_sub = userinfo.get("sub")
    if not oidc_sub:
        return templates.TemplateResponse(
            request,
            "auth/error.html",
            _ERROR_CONTEXT,
            status_code=400,
        )

    email = userinfo.get("email", "")
    display_name = userinfo.get("name") or userinfo.get("preferred_username") or email or "Unknown"

    # Auto-provision or update user (FR39)
    user = uow.users.save(
        oidc_sub=oidc_sub,
        email=email,
        display_name=display_name,
    )
    uow.commit()

    # Create session cookie
    session_value = encode_session(user.id)

    # Redirect to dashboard (or setup wizard in future story 1.4)
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        "session",
        session_value,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=settings.SESSION_MAX_AGE,
    )

    return response


@router.get("/logout")
async def logout():
    """Clear session and redirect to login."""
    response = RedirectResponse("/auth/login", status_code=302)
    response.delete_cookie("session")
    response.delete_cookie("csrf_token")
    return response
