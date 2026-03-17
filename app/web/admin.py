"""Admin endpoints for user lifecycle management."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.dependencies import get_current_user_id, get_uow
from app.domain.models import UserRole
from app.domain.use_cases import users as user_use_cases

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

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
