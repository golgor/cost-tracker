"""Custom Jinja2 filters for template rendering."""

from datetime import datetime
from decimal import Decimal


def format_decimal(value):
    """Format a Decimal as '12.34' (always 2 decimal places)."""
    if value is None:
        return "0.00"
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return f"{float(value):.2f}"


def strftime_filter(value, format_string):
    """Format a date or datetime using strftime."""
    if isinstance(value, datetime):
        return value.strftime(format_string)
    return ""
