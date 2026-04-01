"""Admin view routes for Trips feature."""

import contextlib
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.domain.use_cases import trips as trip_uc
from app.settings import settings
from app.web.expenses._shared import CurrentUserId, UowDep, templates

router = APIRouter(prefix="/trips", tags=["trips"])


@router.get("", response_class=HTMLResponse)
async def trips_dashboard(request: Request, user_id: CurrentUserId, uow: UowDep):
    """Render the main trips dashboard (only trips owned by current user)."""
    with uow:
        user = uow.users.get_by_id(user_id)
        all_trips = uow.trips.list_all()
        my_trips = [t for t in all_trips if t.created_by_id == user_id]
        all_guests = uow.guests.list_all()

    return templates.TemplateResponse(
        request,
        "trips/index.html",
        {
            "user": user,
            "trips": my_trips,
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
    name: Annotated[str, Form()],
    currency: Annotated[str, Form()],
    participant_ids: Annotated[list[int] | None, Form()] = None,
):
    """Create a new trip and return to dashboard."""
    with uow:
        trip_uc.create_trip(uow, name, currency, user_id, participant_ids or [])

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
        trip, participants, expenses = trip_uc.get_trip_details(uow, trip_id)
        trip_uc._assert_trip_owner(trip, user_id)
        all_guests = uow.guests.list_all()

    host_url = str(request.base_url).rstrip("/")
    share_url = f"{host_url}/t/{trip.sharing_token}"

    # Build participant lookup for display
    part_dict = {p.id: p.name for p in participants}

    return templates.TemplateResponse(
        request,
        "trips/admin_detail.html",
        {
            "user": user,
            "trip": trip,
            "participants": participants,
            "expenses": expenses,
            "share_url": share_url,
            "part_dict": part_dict,
            "all_guests": all_guests,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.post("/guests", response_class=HTMLResponse)
async def inline_create_guest(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    guest_name: Annotated[str, Form()],
):
    """Inline creation of a global guest, returns the updated guest list partial."""
    with uow:
        with contextlib.suppress(Exception):
            trip_uc.create_guest(uow, name=guest_name)
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
        trip = uow.trips.get_by_id(trip_id)
        if not trip:
            raise HTTPException(status_code=404)
        trip_uc._assert_trip_owner(trip, user_id)

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


@router.post("/{trip_id}/settle", response_class=HTMLResponse)
async def settle_trip(request: Request, trip_id: int, user_id: CurrentUserId, uow: UowDep):
    """Mark a trip as settled (closed). No more expenses can be added."""
    with uow:
        trip_uc.settle_trip(uow, trip_id, user_id)

    if "hx-request" in request.headers:
        response = HTMLResponse()
        response.headers["HX-Redirect"] = f"/trips/{trip_id}"
        return response
    return RedirectResponse(url=f"/trips/{trip_id}", status_code=303)


@router.get("/{trip_id}/edit", response_class=HTMLResponse)
async def edit_trip_form(request: Request, trip_id: int, user_id: CurrentUserId, uow: UowDep):
    """Render the edit trip form."""
    with uow:
        trip, participants, _expenses = trip_uc.get_trip_details(uow, trip_id)
        trip_uc._assert_trip_owner(trip, user_id)
        all_guests = uow.guests.list_all()

    participant_ids = {p.id for p in participants}

    return templates.TemplateResponse(
        request,
        "trips/_admin_edit_trip.html",
        {
            "trip": trip,
            "participants": participants,
            "all_guests": all_guests,
            "participant_ids": participant_ids,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.post("/{trip_id}/edit", response_class=HTMLResponse)
async def edit_trip(
    request: Request,
    trip_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
    name: Annotated[str, Form()],
    currency: Annotated[str, Form()],
    participant_ids: Annotated[list[int] | None, Form()] = None,
):
    """Update trip details (name, currency, participants)."""
    new_participant_ids = participant_ids or []

    with uow:
        trip_uc.update_trip(uow, trip_id, user_id, name=name, currency=currency)

        # Sync participants: add new, remove old
        current_participants = uow.trips.get_participants(trip_id)
        current_ids = {p.id for p in current_participants}
        desired_ids = set(new_participant_ids)

        to_add = list(desired_ids - current_ids)
        to_remove = current_ids - desired_ids

        if to_add:
            uow.trips.add_participants(trip_id, to_add)
        for gid in to_remove:
            uow.trips.remove_participant(trip_id, gid)

    if "hx-request" in request.headers:
        response = HTMLResponse()
        response.headers["HX-Redirect"] = f"/trips/{trip_id}"
        return response
    return RedirectResponse(url=f"/trips/{trip_id}", status_code=303)


@router.post("/{trip_id}/delete", response_class=HTMLResponse)
async def delete_trip(request: Request, trip_id: int, user_id: CurrentUserId, uow: UowDep):
    """Delete a trip entirely."""
    with uow:
        trip_uc.delete_trip(uow, trip_id, user_id)

    if "hx-request" in request.headers:
        response = HTMLResponse()
        response.headers["HX-Redirect"] = "/trips"
        return response
    return RedirectResponse(url="/trips", status_code=303)


@router.get("/{trip_id}/expenses/{expense_id}/edit", response_class=HTMLResponse)
async def edit_expense_form(
    request: Request,
    trip_id: int,
    expense_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Render the edit expense form partial."""
    with uow:
        trip, participants, _expenses = trip_uc.get_trip_details(uow, trip_id)
        trip_uc._assert_trip_owner(trip, user_id)

        expense = uow.trips.get_expense_by_id(expense_id)
        if not expense or expense.trip_id != trip_id:
            raise HTTPException(status_code=404)

    return templates.TemplateResponse(
        request,
        "trips/_admin_edit_expense.html",
        {
            "trip": trip,
            "expense": expense,
            "participants": participants,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.post("/{trip_id}/expenses/{expense_id}/edit", response_class=HTMLResponse)
async def edit_expense(
    request: Request,
    trip_id: int,
    expense_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
    description: Annotated[str, Form()],
    amount: Annotated[str, Form()],
    paid_by_id: Annotated[int, Form()],
    date_str: Annotated[str, Form(alias="date")] = "",
):
    """Update a trip expense."""
    expense_date = date.fromisoformat(date_str) if date_str else None

    with uow:
        trip_uc.update_expense(
            uow,
            trip_id,
            expense_id,
            user_id,
            description=description,
            amount=Decimal(amount),
            expense_date=expense_date,
            paid_by_id=paid_by_id,
        )

    if "hx-request" in request.headers:
        response = HTMLResponse()
        response.headers["HX-Redirect"] = f"/trips/{trip_id}"
        return response
    return RedirectResponse(url=f"/trips/{trip_id}", status_code=303)


@router.post("/{trip_id}/expenses/{expense_id}/delete", response_class=HTMLResponse)
async def delete_expense(
    request: Request,
    trip_id: int,
    expense_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Delete a trip expense."""
    with uow:
        trip_uc.delete_expense(uow, trip_id, expense_id, user_id)

    if "hx-request" in request.headers:
        response = HTMLResponse()
        response.headers["HX-Redirect"] = f"/trips/{trip_id}"
        return response
    return RedirectResponse(url=f"/trips/{trip_id}", status_code=303)
