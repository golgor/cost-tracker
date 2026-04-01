"""Guest view routes for Trips feature (Magic Links)."""

import json
from decimal import Decimal

from fastapi import APIRouter, Cookie, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from app.domain.use_cases import trips as trip_uc
from app.web.expenses._shared import UowDep, templates

router = APIRouter(tags=["guest_trips"])

# Cookie key containing {trip_id: guest_id} mappings
GUEST_COOKIE = "costtracker_guest_session"


def _get_guest_session(cookie: str | None) -> dict[str, int]:
    """Parse the guest session cookie."""
    if not cookie:
        return {}
    try:
        return json.loads(cookie)
    except json.JSONDecodeError:
        return {}


def _set_guest_session(response: Response, session_data: dict[str, int]) -> None:
    """Set the guest session cookie."""
    response.set_cookie(
        GUEST_COOKIE,
        json.dumps(session_data),
        max_age=60 * 60 * 24 * 60,  # 60 days
        httponly=True,
        samesite="lax",
    )


@router.get("/t/{sharing_token}", response_class=HTMLResponse)
async def guest_landing(
    request: Request,
    sharing_token: str,
    uow: UowDep,
    costtracker_guest_session: str | None = Cookie(None),
):
    """Entry point for magic links. Checks cookie or redirects to identify."""
    with uow:
        trip = uow.trips.get_by_sharing_token(sharing_token)
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")

        session_data = _get_guest_session(costtracker_guest_session)
        trip_str = str(trip.id)

        # If already identified for this trip, go to summary
        if trip_str in session_data:
            return RedirectResponse(url=f"/trips/guest/{trip.id}/summary", status_code=303)

        # Otherwise, render identity selection
        participants = uow.trips.get_participants(trip.id)

    return templates.TemplateResponse(
        request,
        "trips/guest_identify.html",
        {
            "trip": trip,
            "participants": participants,
            "sharing_token": sharing_token,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.post("/trips/guest/{trip_id}/identify", response_class=HTMLResponse)
async def guest_identify(
    request: Request,
    trip_id: int,
    uow: UowDep,
    guest_id: int = Form(...),
    costtracker_guest_session: str | None = Cookie(None),
):
    """Set the session cookie for the selected guest identity."""
    with uow:
        trip = uow.trips.get_by_id(trip_id)
        if not trip:
            raise HTTPException(status_code=404)

        # Verify guest belongs to this trip
        participants = uow.trips.get_participants(trip_id)
        if guest_id not in [p.id for p in participants]:
            raise HTTPException(status_code=403, detail="Invalid guest selection")

    session_data = _get_guest_session(costtracker_guest_session)
    session_data[str(trip_id)] = guest_id

    response = RedirectResponse(url=f"/trips/guest/{trip_id}/summary", status_code=303)
    _set_guest_session(response, session_data)
    return response


@router.get("/trips/guest/{trip_id}/logout", response_class=HTMLResponse)
async def guest_logout(
    request: Request,
    trip_id: int,
    uow: UowDep,
    costtracker_guest_session: str | None = Cookie(None),
):
    """Clear identity for a specific trip and redirect back to the magic link landing."""
    with uow:
        trip = uow.trips.get_by_id(trip_id)
        if not trip:
            raise HTTPException(status_code=404)

    session_data = _get_guest_session(costtracker_guest_session)
    session_data.pop(str(trip_id), None)

    response = RedirectResponse(url=f"/t/{trip.sharing_token}", status_code=303)
    _set_guest_session(response, session_data)
    return response


@router.get("/trips/guest/{trip_id}/summary", response_class=HTMLResponse)
async def guest_summary(
    request: Request,
    trip_id: int,
    uow: UowDep,
    costtracker_guest_session: str | None = Cookie(None),
):
    """The main Guest Trip view."""
    session_data = _get_guest_session(costtracker_guest_session)
    active_guest_id = session_data.get(str(trip_id))

    if not active_guest_id:
        raise HTTPException(status_code=403, detail="Not identified. Please use magic link.")

    with uow:
        try:
            trip, participants, expenses = trip_uc.get_trip_details(uow, trip_id)
        except ValueError:
            raise HTTPException(status_code=404)

        active_guest = next((p for p in participants if p.id == active_guest_id), None)
        if not active_guest:
            raise HTTPException(status_code=403, detail="Guest no longer in trip")

    return templates.TemplateResponse(
        request,
        "trips/guest_summary.html",
        {
            "trip": trip,
            "active_guest": active_guest,
            "participants": participants,
            "expenses": expenses,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.post("/trips/guest/{trip_id}/expenses", response_class=HTMLResponse)
async def add_guest_expense(
    request: Request,
    trip_id: int,
    uow: UowDep,
    description: str = Form(...),
    amount: str = Form(...),
    costtracker_guest_session: str | None = Cookie(None),
):
    """Add a new expense. Handled via standard HTMX POST."""
    session_data = _get_guest_session(costtracker_guest_session)
    active_guest_id = session_data.get(str(trip_id))

    if not active_guest_id:
        raise HTTPException(status_code=403)

    with uow:
        from datetime import date

        trip_uc.add_expense(
            uow,
            trip_id=trip_id,
            description=description,
            amount=Decimal(amount),
            expense_date=date.today(),
            paid_by_id=active_guest_id,
            created_by_guest_id=active_guest_id,
        )

    response = HTMLResponse()
    response.headers["HX-Redirect"] = f"/trips/guest/{trip_id}/summary"
    return response


@router.get("/trips/guest/{trip_id}/balances", response_class=HTMLResponse)
async def guest_balances(
    request: Request,
    trip_id: int,
    uow: UowDep,
    costtracker_guest_session: str | None = Cookie(None),
):
    """Read-only view showing optimized settlements."""
    session_data = _get_guest_session(costtracker_guest_session)
    active_guest_id = session_data.get(str(trip_id))

    if not active_guest_id:
        raise HTTPException(status_code=403)

    with uow:
        trip = uow.trips.get_by_id(trip_id)
        transactions, balances = trip_uc.calculate_trip_settlement(uow, trip_id)
        participants = uow.trips.get_participants(trip_id)
        part_dict = {p.id: p.name for p in participants}

    return templates.TemplateResponse(
        request,
        "trips/guest_balances.html",
        {
            "trip": trip,
            "transactions": transactions,
            "balances": balances,
            "participants": part_dict,
            "active_guest_id": active_guest_id,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )
