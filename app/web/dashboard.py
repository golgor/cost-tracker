from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.dependencies import get_current_user_id, get_uow

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    uow: UnitOfWork = Depends(get_uow),
):
    """Dashboard page - placeholder showing authenticated user info."""
    user = uow.users.get_by_id(user_id)
    return templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "user": user,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )
