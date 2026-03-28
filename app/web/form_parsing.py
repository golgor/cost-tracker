"""Shared form parsing helpers for Decimal amounts, dates, and split configs.

Used by expenses.py and recurring.py to avoid duplicated inline parsing logic.
"""

import json
from datetime import date
from decimal import Decimal, InvalidOperation


def parse_amount(value: str) -> Decimal | None:
    """Parse amount string to Decimal, returning None on failure."""
    try:
        return Decimal(value.replace(",", "."))
    except InvalidOperation, ValueError:
        return None


def parse_date(value: str) -> date | None:
    """Parse ISO date string, returning None on failure."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parse_split_config(value: str) -> dict[int, Decimal] | None:
    """Parse JSON split config string, returning None on failure."""
    if not value:
        return None
    try:
        raw = json.loads(value)
        return {int(k): Decimal(str(v)) for k, v in raw.items()}
    except json.JSONDecodeError, ValueError, KeyError:
        return None
