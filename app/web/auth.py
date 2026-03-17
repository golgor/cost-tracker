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
from app.domain.errors import DuplicateMembershipError, GroupNotFoundError, DeactivatedUserAccessDenied
from app.domain.models import MemberRole
from app.domain.use_cases import groups as group_use_cases
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


@router.get("/callback")
async def callback(request: Request, uow: UowDep):
    """Handle OIDC callback, provision user if needed, create session."""
    oauth = get_oauth()

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

    # Provision/update user with deactivation check via use case
    try:
        user = user_use_cases.provision_user(
            uow,
            oidc_sub=oidc_sub,
            email=email,
            display_name=display_name,
            actor_id=1,  # Use system actor for OIDC provisioning (no user context yet)
        )
    except DeactivatedUserAccessDenied:
        logger.info("Deactivated user %s attempted login", oidc_sub)
        return templates.TemplateResponse(
            request,
            "auth/error.html",
            {
                "csrf_token": "",
                "message": "Your account is deactivated. Please contact an administrator.",
            },
            status_code=403,
        )

    # Check if first user needs admin bootstrap
    if uow.users.count_active_admins() == 0:
        # First user gets admin role
        user = uow.users.promote_to_admin(user.id, actor_id=user.id)
        uow.commit()

    # Create session cookie
    session_value = encode_session(user.id)

    # Determine redirect based on admin bootstrap state (Story 1.4)
    existing_group = uow.groups.get_by_user_id(user.id)
    if existing_group:
        # User already in a group → dashboard
        redirect_url = "/"
    elif not uow.groups.has_active_admin():
        # No active admin exists → redirect to setup wizard (first admin bootstrap)
        redirect_url = "/setup"
    else:
        # Active admin exists → auto-provision as regular user via domain use case
        group = uow.groups.get_default_group()
        if group is None:
            raise GroupNotFoundError("Active admin exists but no default group found")

        try:
            group_use_cases.add_member(
                uow=uow,
                group_id=group.id,
                user_id=user.id,
                role=MemberRole.USER,
            )
            logger.info("Auto-provisioned user %d to group %d as USER", user.id, group.id)
        except DuplicateMembershipError:
            logger.info(
                "User %d already had membership in group %d during callback auto-provision",
                user.id,
                group.id,
            )
        redirect_url = "/"

    response = RedirectResponse(redirect_url, status_code=302)
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
