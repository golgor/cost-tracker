"""Route handlers for the recurring definitions registry."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from app.adapters.sqlalchemy.queries.recurring_queries import (
    get_active_definitions,
    get_paused_definitions,
    get_registry_summary,
)
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.dependencies import get_current_user_id, get_uow
from app.web.templates import setup_templates

router = APIRouter(tags=["recurring"])
templates = setup_templates("app/templates")

CurrentUserId = Annotated[int, Depends(get_current_user_id)]
UowDep = Annotated[UnitOfWork, Depends(get_uow)]


@router.get("/recurring", response_class=HTMLResponse)
async def registry_index(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Render the recurring definitions registry (Active tab by default)."""
    with uow:
        group = uow.groups.get_by_user_id(user_id)
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No household group found",
            )
        user = uow.users.get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        definitions = get_active_definitions(uow.session, group.id)
        summary = get_registry_summary(uow.session, group.id)

    return templates.TemplateResponse(
        request,
        "recurring/index.html",
        {
            "user": user,
            "group": group,
            "definitions": definitions,
            "summary": summary,
            "active_tab": "active",
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.get("/recurring/tab/{tab}", response_class=HTMLResponse)
async def registry_tab(
    request: Request,
    tab: str,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """HTMX partial: switch between Active and Paused tabs."""
    if tab not in ("active", "paused"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tab")

    with uow:
        group = uow.groups.get_by_user_id(user_id)
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No household group found",
            )

        if tab == "active":
            definitions = get_active_definitions(uow.session, group.id)
        else:
            definitions = get_paused_definitions(uow.session, group.id)

        summary = get_registry_summary(uow.session, group.id)

    return templates.TemplateResponse(
        request,
        "recurring/_definition_list.html",
        {
            "definitions": definitions,
            "summary": summary,
            "active_tab": tab,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )
