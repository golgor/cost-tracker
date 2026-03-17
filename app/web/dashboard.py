from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.dependencies import get_current_user_id, get_uow

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")

CurrentUserId = Annotated[int, Depends(get_current_user_id)]
UowDep = Annotated[UnitOfWork, Depends(get_uow)]


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Dashboard page - placeholder showing authenticated user info."""
    user = uow.users.get_by_id(user_id)
    return templates.TemplateResponse(
        request,
        "dashboard/index.html",
        {
            "user": user,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )
