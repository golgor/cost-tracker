import logging
from typing import Annotated

from authlib.integrations.base_client.errors import MismatchingStateError
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.auth.oidc import get_oauth
from app.auth.session import encode_session
from app.dependencies import get_uow
from app.domain.use_cases import users as user_use_cases
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


def _extract_user_info_from_token(token: dict) -> tuple[str, str, str]:
    """Extract oidc_sub, email, and display_name from OAuth token.

    Raises ValueError if oidc_sub is missing.
    Returns (oidc_sub, email, display_name).
    """
    userinfo = token.get("userinfo", {})
    oidc_sub = userinfo.get("sub")
    if not oidc_sub:
        raise ValueError("Missing OIDC sub claim in token")

    email = userinfo.get("email", "")
    display_name = userinfo.get("name") or userinfo.get("preferred_username") or email or "Unknown"

    return oidc_sub, email, display_name


@router.get("/callback")
async def callback(request: Request, uow: UowDep):
    """Handle OIDC callback, provision user if needed, create session."""
    oauth = get_oauth()

    # Step 1: Get OAuth token and handle errors
    try:
        token = await oauth.authentik.authorize_access_token(request)
    except MismatchingStateError:
        # Stale session cookie - clear it and restart login flow
        logger.warning("OAuth state mismatch - clearing session and restarting login")
        response = RedirectResponse("/auth/login", status_code=302)
        response.delete_cookie("session", path="/")
        response.delete_cookie("cost_tracker_session", path="/")
        return response
    except Exception as e:
        logger.error("OIDC callback failed: %s", e, exc_info=True)
        return templates.TemplateResponse(
            request,
            "auth/error.html",
            _ERROR_CONTEXT,
            status_code=400,
        )

    # Step 2: Extract user info from token
    try:
        oidc_sub, email, display_name = _extract_user_info_from_token(token)
    except ValueError:
        return templates.TemplateResponse(
            request,
            "auth/error.html",
            _ERROR_CONTEXT,
            status_code=400,
        )

    # Step 3: Check if user exists or provision new user
    with uow:
        existing_user = uow.users.get_by_oidc_sub(oidc_sub)

        if existing_user is not None:
            user = existing_user
        else:
            # New user — check MAX_USERS limit
            if uow.users.count() >= settings.MAX_USERS:
                logger.warning(
                    "User limit reached (%d), rejecting new user with sub=%s",
                    settings.MAX_USERS,
                    oidc_sub,
                )
                return templates.TemplateResponse(
                    request,
                    "auth/error.html",
                    {
                        "csrf_token": "",
                        "error_message": (
                            f"User limit reached. This instance only allows "
                            f"{settings.MAX_USERS} users."
                        ),
                    },
                    status_code=403,
                )

            user = user_use_cases.provision_user(
                uow,
                oidc_sub=oidc_sub,
                email=email,
                display_name=display_name,
            )

    # Step 4: Trigger auto-generation on login (best-effort, limit to avoid slow logins)
    try:
        from datetime import date

        from app.web.api_internal import run_auto_generation

        run_auto_generation(uow.session, date.today())
    except Exception:
        logger.warning("Auto-generation on login failed (non-fatal)", exc_info=True)

    # Step 5: Create session cookie and redirect
    session_value = encode_session(user.id)
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        "cost_tracker_session",
        session_value,
        path="/",
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
    response.delete_cookie("cost_tracker_session", path="/")
    response.delete_cookie("session", path="/")  # Clear Starlette OAuth state
    response.delete_cookie("csrf_token")
    return response
