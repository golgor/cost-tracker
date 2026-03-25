from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.dependencies import get_current_user_id, get_uow
from app.web.templates import setup_templates

router = APIRouter(tags=["dashboard"])
templates = setup_templates("app/templates")

CurrentUserId = Annotated[int, Depends(get_current_user_id)]
UowDep = Annotated[UnitOfWork, Depends(get_uow)]


@router.get("/", response_class=HTMLResponse)
async def root_redirect(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Redirect root to expenses list.

    The dashboard has been removed; /expenses is the canonical expense management page.
    """
    with uow:
        user_domain = uow.users.get_by_id(user_id)
        if user_domain is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Get user's primary group (MVP1: single household per user)
        group = uow.groups.get_by_user_id(user_id)
        if group is None:
            # Redirect to setup wizard if no group exists
            return templates.TemplateResponse(
                request,
                "dashboard/empty_state_setup.html",
                {
                    "user": user_domain,
                    "csrf_token": getattr(request.state, "csrf_token", ""),
                },
            )

    # Redirect to expenses list
    return RedirectResponse(url="/expenses", status_code=307)
