"""Admin endpoints for user lifecycle management."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.adapters.sqlalchemy.queries import get_all_users, get_recent_audit_entries
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.dependencies import get_current_user_id, get_uow
from app.domain.models import UserRole
from app.domain.use_cases import users as user_use_cases

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")

UowDep = Annotated[UnitOfWork, Depends(get_uow)]
CurrentUserId = Annotated[int, Depends(get_current_user_id)]


def _check_admin_access(user_id: int, uow: UnitOfWork) -> None:
    """Check if user has admin role."""
    user = uow.users.get_by_id(user_id)
    if not user or user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can perform this action",
        )


# HTML pages for admin UI
@router.get("/users", response_class=HTMLResponse)
async def admin_users_page(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Admin user management page."""
    _check_admin_access(user_id, uow)

    # Fetch all users for display
    users = get_all_users(uow.session)
    user = uow.users.get_by_id(user_id)
    return templates.TemplateResponse(
        request,
        "admin/users.html",
        {
            "user": user,
            "users": users,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.get("/audit", response_class=HTMLResponse)
async def admin_audit_log_page(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Admin audit log page."""
    _check_admin_access(user_id, uow)

    # TODO: Fetch audit log entries
    user = uow.users.get_by_id(user_id)
    return templates.TemplateResponse(
        request,
        "admin/audit.html",
        {
            "user": user,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


# API endpoints for user lifecycle management

@router.post("/users/{target_user_id}/promote")
async def promote_user(target_user_id: int, actor_id: CurrentUserId, uow: UowDep):
    """Promote user to admin role."""
    _check_admin_access(actor_id, uow)

    user_use_cases.promote_user_to_admin(uow, target_user_id, actor_id=actor_id)
    return JSONResponse(
        {"success": True, "message": f"User {target_user_id} promoted to admin"},
        status_code=200,
    )


@router.post("/users/{target_user_id}/demote")
async def demote_user(target_user_id: int, actor_id: CurrentUserId, uow: UowDep):
    """Demote admin to regular user role."""
    _check_admin_access(actor_id, uow)

    user_use_cases.demote_user_to_regular(uow, target_user_id, actor_id=actor_id)
    return JSONResponse(
        {"success": True, "message": f"User {target_user_id} demoted to regular user"},
        status_code=200,
    )


@router.post("/users/{target_user_id}/deactivate")
async def deactivate_user(target_user_id: int, actor_id: CurrentUserId, uow: UowDep):
    """Deactivate a user."""
    _check_admin_access(actor_id, uow)

    user_use_cases.deactivate_user(uow, target_user_id, actor_id=actor_id)
    return JSONResponse(
        {"success": True, "message": f"User {target_user_id} deactivated"},
        status_code=200,
    )


@router.post("/users/{target_user_id}/reactivate")
async def reactivate_user(target_user_id: int, actor_id: CurrentUserId, uow: UowDep):
    """Reactivate a deactivated user."""
    _check_admin_access(actor_id, uow)

    user_use_cases.reactivate_user(uow, target_user_id, actor_id=actor_id)
    return JSONResponse(
        {"success": True, "message": f"User {target_user_id} reactivated"},
        status_code=200,
    )

# HTMX endpoints for action buttons
@router.post("/users/{target_user_id}/promote")
async def promote_user_htmx(
    target_user_id: int,
    request: Request,
    actor_id: CurrentUserId,
    uow: UowDep,
):
    """Promote user (HTMX response)."""
    _check_admin_access(actor_id, uow)

    user_use_cases.promote_user_to_admin(uow, target_user_id, actor_id=actor_id)
    # Return updated row
    users = get_all_users(uow.session)
    user = [u for u in users if u.id == target_user_id][0]
    return templates.TemplateResponse(
        request,
        "admin/_user_row.html",
        {"u": user},
    )


@router.post("/users/{target_user_id}/demote")
async def demote_user_htmx(
    target_user_id: int,
    request: Request,
    actor_id: CurrentUserId,
    uow: UowDep,
):
    """Demote user (HTMX response)."""
    _check_admin_access(actor_id, uow)

    user_use_cases.demote_user_to_regular(uow, target_user_id, actor_id=actor_id)
    users = get_all_users(uow.session)
    user = [u for u in users if u.id == target_user_id][0]
    return templates.TemplateResponse(
        request,
        "admin/_user_row.html",
        {"u": user},
    )


@router.get("/users/{target_user_id}/deactivate-confirm", response_class=HTMLResponse)
async def deactivate_confirm_dialog(
    target_user_id: int,
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Show deactivate confirmation dialog."""
    _check_admin_access(user_id, uow)

    target_user = uow.users.get_by_id(target_user_id)
    return templates.TemplateResponse(
        request,
        "admin/_deactivate_confirm.html",
        {"target_user": target_user, "csrf_token": getattr(request.state, "csrf_token", "")},
    )


@router.post("/users/{target_user_id}/deactivate")
async def deactivate_user_htmx(
    target_user_id: int,
    request: Request,
    actor_id: CurrentUserId,
    uow: UowDep,
):
    """Deactivate user (HTMX response)."""
    _check_admin_access(actor_id, uow)

    user_use_cases.deactivate_user(uow, target_user_id, actor_id=actor_id)
    users = get_all_users(uow.session)
    user = [u for u in users if u.id == target_user_id][0]
    return templates.TemplateResponse(
        request,
        "admin/_user_row.html",
        {"u": user},
    )


@router.post("/users/{target_user_id}/reactivate")
async def reactivate_user_htmx(
    target_user_id: int,
    request: Request,
    actor_id: CurrentUserId,
    uow: UowDep,
):
    """Reactivate user (HTMX response)."""
    _check_admin_access(actor_id, uow)

    user_use_cases.reactivate_user(uow, target_user_id, actor_id=actor_id)
    users = get_all_users(uow.session)
    user = [u for u in users if u.id == target_user_id][0]
    return templates.TemplateResponse(
        request,
        "admin/_user_row.html",
        {"u": user},
    )
