from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.dependencies import get_current_user_id, get_uow

router = APIRouter(tags=["dashboard"])

CurrentUserId = Annotated[int, Depends(get_current_user_id)]
UowDep = Annotated[UnitOfWork, Depends(get_uow)]


@router.get("/", response_class=HTMLResponse)
async def root_redirect(
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Redirect root to expenses list."""
    with uow:
        user_domain = uow.users.get_by_id(user_id)
        if user_domain is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return RedirectResponse(url="/expenses", status_code=307)
