# Add a Route

How to add a new page or HTMX endpoint to Cost Tracker.

## Route File Structure

Routes live in `app/web/` and are registered in `app/web/router.py`. Each route file defines
an `APIRouter` and handles a feature area.

## Standard Page Route

```python
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.dependencies import get_current_user_id, get_uow

router = APIRouter(tags=["widgets"])

CurrentUserId = Annotated[int, Depends(get_current_user_id)]
UowDep = Annotated[UnitOfWork, Depends(get_uow)]


@router.get("/widgets", response_class=HTMLResponse)
async def widget_list(request: Request, user_id: CurrentUserId, uow: UowDep):
    """List all widgets for the user's group."""
    group = uow.groups.get_by_user_id(user_id)
    widgets = uow.queries.widget_list(group.id)  # Read-only query

    return request.app.state.templates.TemplateResponse(
        "widgets/list.html",
        {"request": request, "widgets": widgets},
    )
```

## Form Submission Route

Use `Annotated[T, Form()]` for form parameters — never manual `await request.form()`:

```python
from fastapi.params import Form


@router.post("/widgets/create", response_class=HTMLResponse)
async def create_widget(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    name: Annotated[str, Form()],
    amount: Annotated[str, Form()],
    date_str: Annotated[str, Form(alias="date")],  # alias when HTML name differs
):
    """Create a new widget."""
    with uow:
        widget = create_widget_use_case(
            uow=uow,
            group_id=group.id,
            actor_id=user_id,
            name=name,
            amount=Decimal(amount),
        )

    return RedirectResponse(url="/widgets", status_code=303)
```

Rules:

- Always use `Annotated[T, Form()]` — never `T = Form(...)`
- Use `alias` when the HTML field name differs from the Python name
- Wrap mutations in `with uow:` for transaction management
- Redirect after POST (POST/Redirect/GET pattern)

## HTMX Partial Route

HTMX endpoints return HTML fragments, not full pages. They share paths with page routes,
distinguished by the `HX-Request` header:

```python
@router.get("/widgets/{widget_id}/detail", response_class=HTMLResponse)
async def widget_detail(
    request: Request,
    widget_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Expand widget detail (HTMX partial)."""
    widget = uow.queries.widget_detail(widget_id)
    return request.app.state.templates.TemplateResponse(
        "widgets/_detail.html",  # Partial templates prefixed with _
        {"request": request, "widget": widget},
    )
```

HTMX partial templates are prefixed with `_` (e.g., `_detail.html`, `_row.html`).

## Error Handling

Do **not** add `try/except` for domain errors in route handlers. The global exception handler in
`main.py` maps `DomainError` subclasses to HTTP responses via `DOMAIN_ERROR_MAP`. Just call the
use case — if it raises a domain error, the handler returns the appropriate HTTP status.

To add a new domain error response, add an entry to `DOMAIN_ERROR_MAP` in `app/main.py`:

```python
DOMAIN_ERROR_MAP = {
    WidgetNotFoundError: 404,
    DuplicateWidgetError: 409,
}
```

## Read-Only Queries

For display-only routes (no mutations), call view queries directly instead of use cases:

```python
@router.get("/widgets", response_class=HTMLResponse)
async def widget_list(request: Request, user_id: CurrentUserId, uow: UowDep):
    widgets = uow.queries.widget_list(group.id)  # Direct query, no use case
    return request.app.state.templates.TemplateResponse(...)
```

View queries live in `app/adapters/sqlalchemy/queries/` and are strictly read-only (enforced by
architecture tests).

## Register the Router

Add your router to `app/web/router.py`:

```python
from app.web.widgets import router as widgets_router

api_router.include_router(widgets_router)
```

## Template Conventions

- Templates: `app/templates/widgets/list.html` (snake_case)
- HTMX partials: `app/templates/widgets/_detail.html` (prefixed with `_`)
- No value comparisons in templates — use pre-computed boolean flags
- Only boolean checks: `{% if widget.is_active %}`, never `{% if widget.status == "active" %}`
