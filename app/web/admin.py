"""Admin endpoints for user management."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.adapters.sqlalchemy.queries import get_all_users
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.dependencies import get_current_user_id, get_uow
from app.web.view_models import UserProfileViewModel, UserRowViewModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")

UowDep = Annotated[UnitOfWork, Depends(get_uow)]
CurrentUserId = Annotated[int, Depends(get_current_user_id)]


# HTML pages for admin UI
@router.get("/users", response_class=HTMLResponse)
async def admin_users_page(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Admin user management page."""
    # Fetch all users for display
    users_domain = get_all_users(uow.session)
    user_domain = uow.users.get_by_id(user_id)
    if user_domain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    users_view = [UserRowViewModel.from_domain(u) for u in users_domain]
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
