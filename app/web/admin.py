"""Admin endpoints for user lifecycle management."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.adapters.sqlalchemy.queries import get_all_users
from app.adapters.sqlalchemy.queries.admin_queries import get_recent_audit_entries
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.dependencies import get_current_user_id, get_uow
from app.domain.models import UserRole
from app.domain.use_cases import users as user_use_cases
from app.web.view_models import AuditEntryViewModel, UserProfileViewModel, UserRowViewModel

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
    users_domain = get_all_users(uow.session)
    user_domain = uow.users.get_by_id(user_id)

    # Count active admins to determine demote button visibility
    active_admin_count = sum(1 for u in users_domain if u.role == UserRole.ADMIN and u.is_active)

    # Transform to view models with active admin count context
    users_view = [
        UserRowViewModel.from_domain(u, active_admin_count=active_admin_count) for u in users_domain
    ]
    user_view = UserProfileViewModel.from_domain(user_domain)

    return templates.TemplateResponse(
        request,
        "admin/users.html",
        {
            "user": user_view,
            "users": users_view,
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

    user_domain = uow.users.get_by_id(user_id)
    audit_entries_dicts = get_recent_audit_entries(uow.session, limit=100)

    # Transform to view models
    user_view = UserProfileViewModel.from_domain(user_domain)
    audit_entries_view = [AuditEntryViewModel.from_dict(e) for e in audit_entries_dicts]

    return templates.TemplateResponse(
        request,
        "admin/audit.html",
        {
            "user": user_view,
            "audit_entries": audit_entries_view,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


# HTMX endpoints for user lifecycle actions


@router.post("/users/{target_user_id}/promote")
async def promote_user(
    target_user_id: int,
    request: Request,
    actor_id: CurrentUserId,
    uow: UowDep,
):
    """Promote user to admin role."""
    _check_admin_access(actor_id, uow)

    with uow:
        user_use_cases.promote_user_to_admin(uow, target_user_id, actor_id=actor_id)
        # Return updated row
        user_domain = uow.users.get_by_id(target_user_id)
        user_view = UserRowViewModel.from_domain(user_domain)

    return templates.TemplateResponse(
        request,
        "admin/_user_row.html",
        {"u": user_view},
    )


@router.post("/users/{target_user_id}/demote")
async def demote_user(
    target_user_id: int,
    request: Request,
    actor_id: CurrentUserId,
    uow: UowDep,
):
    """Demote admin to regular user role."""
    _check_admin_access(actor_id, uow)

    with uow:
        user_use_cases.demote_user_to_regular(uow, target_user_id, actor_id=actor_id)
        user_domain = uow.users.get_by_id(target_user_id)
        user_view = UserRowViewModel.from_domain(user_domain)

    return templates.TemplateResponse(
        request,
        "admin/_user_row.html",
        {"u": user_view},
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

    target_user_domain = uow.users.get_by_id(target_user_id)
    target_user_view = UserProfileViewModel.from_domain(target_user_domain)

    return templates.TemplateResponse(
        request,
        "admin/_deactivate_confirm.html",
        {
            "target_user": target_user_view,
            "target_user_id": target_user_id,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.post("/users/{target_user_id}/deactivate")
async def deactivate_user(
    target_user_id: int,
    request: Request,
    actor_id: CurrentUserId,
    uow: UowDep,
):
    """Deactivate a user."""
    _check_admin_access(actor_id, uow)

    with uow:
        user_use_cases.deactivate_user(uow, target_user_id, actor_id=actor_id)
        user_domain = uow.users.get_by_id(target_user_id)
        user_view = UserRowViewModel.from_domain(user_domain)

    return templates.TemplateResponse(
        request,
        "admin/_user_row.html",
        {"u": user_view},
    )


@router.post("/users/{target_user_id}/reactivate")
async def reactivate_user(
    target_user_id: int,
    request: Request,
    actor_id: CurrentUserId,
    uow: UowDep,
):
    """Reactivate a deactivated user."""
    _check_admin_access(actor_id, uow)

    with uow:
        user_use_cases.reactivate_user(uow, target_user_id, actor_id=actor_id)
        user_domain = uow.users.get_by_id(target_user_id)
        user_view = UserRowViewModel.from_domain(user_domain)

    return templates.TemplateResponse(
        request,
        "admin/_user_row.html",
        {"u": user_view},
    )
