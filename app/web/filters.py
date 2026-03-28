"""Custom Jinja2 filters for template rendering."""

from datetime import date, datetime
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
    if isinstance(value, (date, datetime)):
        return value.strftime(format_string)
    return ""


CURRENCY_SYMBOLS: dict[str, str] = {
    "EUR": "€",
    "USD": "$",
    "GBP": "£",
    "SEK": "kr",
}


def get_currency_symbol(currency_code: str) -> str:
    """Get currency symbol for a given currency code.

    Args:
        currency_code: ISO 4217 currency code (e.g., 'EUR', 'USD')

    Returns:
        Currency symbol (e.g., '€', '$') or the code itself if unknown
    """
    if not currency_code:
        return ""
    return CURRENCY_SYMBOLS.get(currency_code.upper(), currency_code)


def currency_symbol_filter(currency_code: str) -> str:
    """Jinja2 filter: convert a currency code to its symbol.

    Args:
        currency_code: ISO 4217 currency code (e.g., 'EUR', 'USD')

    Returns:
        Currency symbol (e.g., '€', '$') or the code itself if unknown
    """
    return get_currency_symbol(currency_code)
