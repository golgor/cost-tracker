"""Admin view routes for Trips feature."""

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.domain.use_cases import trips as trip_uc
from app.settings import settings
from app.web.expenses._shared import CurrentUserId, UowDep, templates

router = APIRouter(prefix="/trips", tags=["trips"])


@router.get("", response_class=HTMLResponse)
async def trips_dashboard(request: Request, user_id: CurrentUserId, uow: UowDep):
    """Render the main trips dashboard."""
    with uow:
        user = uow.users.get_by_id(user_id)
        all_trips = uow.trips.list_all()
        all_guests = uow.guests.list_all()

    return templates.TemplateResponse(
        request,
        "trips/index.html",
        {
            "user": user,
            "trips": all_trips,
            "guests": all_guests,
            "default_currency": settings.DEFAULT_CURRENCY,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.post("", response_class=HTMLResponse)
async def create_trip(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    name: str = Form(...),
    currency: str = Form(...),
    participant_ids: list[int] = Form(default=[]),
):
    """Create a new trip and return to dashboard."""
    with uow:
        trip_uc.create_trip(uow, name, currency, user_id, participant_ids)

    # Redirect using HX-Redirect if HTMX request, else standard redirect
    if "hx-request" in request.headers:
        response = HTMLResponse()
        response.headers["HX-Redirect"] = "/trips"
        return response
    return RedirectResponse(url="/trips", status_code=303)


@router.get("/{trip_id}", response_class=HTMLResponse)
async def trip_detail(request: Request, trip_id: int, user_id: CurrentUserId, uow: UowDep):
    """Render the detailed view for an admin managing a trip."""
    with uow:
        user = uow.users.get_by_id(user_id)
        try:
            trip, participants, expenses = trip_uc.get_trip_details(uow, trip_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Trip not found")

    # Generate the sharing URL
    host_url = str(request.base_url).rstrip("/")
    share_url = f"{host_url}/t/{trip.sharing_token}"

    return templates.TemplateResponse(
        request,
        "trips/admin_detail.html",
        {
            "user": user,
            "trip": trip,
            "participants": participants,
            "expenses": expenses,
            "share_url": share_url,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.post("/guests", response_class=HTMLResponse)
async def inline_create_guest(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    guest_name: str = Form(...),
):
    """Inline creation of a global guest, returns the updated guest list partial."""
    with uow:
        try:
            trip_uc.create_guest(uow, name=guest_name)
        except Exception:
            # Handle unique constraint violation silently for now in UI
            pass
        all_guests = uow.guests.list_all()

    return templates.TemplateResponse(
        request,
        "trips/_guest_list_checkboxes.html",
        {"guests": all_guests},
    )


@router.get("/{trip_id}/settlement", response_class=HTMLResponse)
async def trip_settlement_preview(
    request: Request, trip_id: int, user_id: CurrentUserId, uow: UowDep
):
    """Preview the optimal settlement transactions for a trip."""
    with uow:
        transactions, balances = trip_uc.calculate_trip_settlement(uow, trip_id)
        participants = uow.trips.get_participants(trip_id)
        part_dict = {p.id: p.name for p in participants}

    return templates.TemplateResponse(
        request,
        "trips/_admin_settlement_preview.html",
        {
            "transactions": transactions,
            "balances": balances,
            "participants": part_dict,
        },
    )
