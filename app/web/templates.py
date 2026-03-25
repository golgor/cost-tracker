"""Shared Jinja2 templates configuration for all routers."""

from fastapi.templating import Jinja2Templates

from app.web.filters import (
    currency_symbol_filter,
    format_decimal,
    strftime_filter,
)


def setup_templates(directory: str) -> Jinja2Templates:
    """Create and configure Jinja2Templates with custom filters.

    Usage:
        templates = setup_templates("app/templates")
    """
    templates = Jinja2Templates(directory=directory)
    templates.env.filters["format_decimal"] = format_decimal
    templates.env.filters["strftime"] = strftime_filter
    templates.env.filters["currency_symbol"] = currency_symbol_filter
    return templates
