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


def currency_symbol_filter(currency_code: str) -> str:
    """Convert a currency code to its symbol.

    Args:
        currency_code: ISO 4217 currency code (e.g., 'EUR', 'USD')

    Returns:
        Currency symbol (e.g., '€', '$') or the code itself if unknown
    """
    if not currency_code:
        return ""

    currency_symbols = {
        "EUR": "€",
        "USD": "$",
        "GBP": "£",
        "SEK": "kr",
    }
    return currency_symbols.get(currency_code.upper(), currency_code)
