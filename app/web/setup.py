import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.dependencies import get_current_user_id, get_uow
from app.domain.errors import (
    DuplicateHouseholdError,
    DuplicateMembershipError,
)
from app.domain.models import SplitType
from app.domain.use_cases import groups as group_use_cases

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/setup", tags=["setup"])
templates = Jinja2Templates(directory="app/templates")

CurrentUserId = Annotated[int, Depends(get_current_user_id)]
UowDep = Annotated[UnitOfWork, Depends(get_uow)]

SUPPORTED_CURRENCIES = ["EUR", "USD", "GBP", "SEK", "NOK", "DKK", "CHF"]


@router.get("", response_class=HTMLResponse)
async def setup_redirect(request: Request, user_id: CurrentUserId, uow: UowDep):
    """Redirect to appropriate setup step based on user state."""
    user = uow.users.get_by_id(user_id)
    if not user:
        return RedirectResponse("/auth/login", status_code=302)

    group = uow.groups.get_by_user_id(user_id)
    if group:
        return RedirectResponse("/", status_code=302)

    return RedirectResponse("/setup/step-1", status_code=302)


@router.get("/step-1", response_class=HTMLResponse)
async def setup_step_1(request: Request, user_id: CurrentUserId, uow: UowDep):
    """Step 1: Profile confirmation - display OIDC claims for verification."""
    user = uow.users.get_by_id(user_id)
    if not user:
        return RedirectResponse("/auth/login", status_code=302)

    group = uow.groups.get_by_user_id(user_id)
    if group:
        return RedirectResponse("/", status_code=302)

    return templates.TemplateResponse(
        request,
        "setup/step_1.html",
        {
            "user": user,
            "current_step": 1,
            "total_steps": 3,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.post("/step-1", response_class=HTMLResponse)
async def setup_step_1_post(request: Request, user_id: CurrentUserId, uow: UowDep):
    """Step 1: Proceed to step 2 after profile confirmation."""
    user = uow.users.get_by_id(user_id)
    if not user:
        return RedirectResponse("/auth/login", status_code=302)

    group = uow.groups.get_by_user_id(user_id)
    if group:
        return RedirectResponse("/", status_code=302)

    return RedirectResponse("/setup/step-2", status_code=302)


@router.get("/step-2", response_class=HTMLResponse)
async def setup_step_2(request: Request, user_id: CurrentUserId, uow: UowDep):
    """Step 2: Household creation form."""
    user = uow.users.get_by_id(user_id)
    if not user:
        return RedirectResponse("/auth/login", status_code=302)

    group = uow.groups.get_by_user_id(user_id)
    if group:
        return RedirectResponse("/", status_code=302)

    return templates.TemplateResponse(
        request,
        "setup/step_2.html",
        {
            "user": user,
            "current_step": 2,
            "total_steps": 3,
            "csrf_token": getattr(request.state, "csrf_token", ""),
            "errors": {},
        },
    )


@router.post("/step-2", response_class=HTMLResponse)
async def setup_step_2_post(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    household_name: str = Form(...),
):
    """Step 2: Create household group and proceed to step 3."""
    user = uow.users.get_by_id(user_id)
    if not user:
        return RedirectResponse("/auth/login", status_code=302)

    group = uow.groups.get_by_user_id(user_id)
    if group:
        return RedirectResponse("/", status_code=302)

    errors = {}
    normalized_household_name = household_name.strip()
    if not normalized_household_name or len(normalized_household_name) < 2:
        errors["household_name"] = "Household name must be at least 2 characters"
    elif len(normalized_household_name) > 100:
        errors["household_name"] = "Household name must be at most 100 characters"

    if errors:
        return templates.TemplateResponse(
            request,
            "setup/step_2.html",
            {
                "user": user,
                "current_step": 2,
                "total_steps": 3,
                "csrf_token": getattr(request.state, "csrf_token", ""),
                "errors": errors,
                "household_name": household_name,
            },
        )

    try:
        group = group_use_cases.create_household(
            uow=uow,
            user_id=user_id,
            name=normalized_household_name,
            default_currency="EUR",
            default_split_type=SplitType.EVEN,
        )
    except DuplicateHouseholdError, DuplicateMembershipError:
        # Idempotent behavior for concurrent setup/login flows.
        group = uow.groups.get_by_user_id(user_id)
        if group is not None:
            return RedirectResponse("/", status_code=302)
        return RedirectResponse("/setup/step-1", status_code=302)

    logger.info("User %d completed household creation for group %d", user_id, group.id)

    return RedirectResponse("/setup/step-3", status_code=302)


def _build_split_type_options() -> list[dict[str, str]]:
    """Build split type options with display text (removes logic from template)."""
    return [
        {"value": SplitType.EVEN.value, "display": "Even (50/50)"}
    ]


@router.get("/step-3", response_class=HTMLResponse)
async def setup_step_3(request: Request, user_id: CurrentUserId, uow: UowDep):
    """Step 3: Configuration form (currency, split mode, threshold)."""
    user = uow.users.get_by_id(user_id)
    if not user:
        return RedirectResponse("/auth/login", status_code=302)

    group = uow.groups.get_by_user_id(user_id)
    if not group:
        return RedirectResponse("/setup/step-1", status_code=302)

    return templates.TemplateResponse(
        request,
        "setup/step_3.html",
        {
            "user": user,
            "group": group,
            "current_step": 3,
            "total_steps": 3,
            "csrf_token": getattr(request.state, "csrf_token", ""),
            "currencies": SUPPORTED_CURRENCIES,
            "split_type_options": _build_split_type_options(),
            "errors": {},
        },
    )


@router.post("/step-3", response_class=HTMLResponse)
async def setup_step_3_post(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    default_currency: str = Form(...),
    default_split_type: str = Form(...),
    tracking_threshold: int = Form(...),
):
    """Step 3: Save configuration and redirect to dashboard."""
    user = uow.users.get_by_id(user_id)
    if not user:
        return RedirectResponse("/auth/login", status_code=302)

    group = uow.groups.get_by_user_id(user_id)
    if not group:
        return RedirectResponse("/setup/step-1", status_code=302)

    errors = {}
    if default_currency not in SUPPORTED_CURRENCIES:
        errors["default_currency"] = "Invalid currency selected"

    try:
        split_type = SplitType(default_split_type)
    except ValueError:
        errors["default_split_type"] = "Invalid split type selected"
        split_type = SplitType.EVEN

    if tracking_threshold < 1 or tracking_threshold > 365:
        errors["tracking_threshold"] = "Tracking threshold must be between 1 and 365"

    if errors:
        return templates.TemplateResponse(
            request,
            "setup/step_3.html",
            {
                "user": user,
                "group": group,
                "current_step": 3,
                "total_steps": 3,
                "csrf_token": getattr(request.state, "csrf_token", ""),
                "currencies": SUPPORTED_CURRENCIES,
                "split_type_options": _build_split_type_options(),
                "errors": errors,
                "default_currency": default_currency,
                "default_split_type": default_split_type,
                "tracking_threshold": tracking_threshold,
            },
        )

    with uow:
        group_use_cases.update_group_defaults(
            uow=uow,
            actor_user_id=user_id,
            group_id=group.id,
            default_currency=default_currency,
            default_split_type=split_type,
            tracking_threshold=tracking_threshold,
        )

    logger.info("User %d completed setup wizard for group %d", user_id, group.id)

    return RedirectResponse("/", status_code=302)
