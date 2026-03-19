"""Utility for computing field-level changes from SQLAlchemy's dirty tracking.

Uses ``inspect()`` to read attribute history on ORM rows that have been mutated
but not yet flushed. Returns a dict of ``{field: {"old": ..., "new": ...}}``
suitable for persisting in the audit log ``changes`` JSON column.

This module lives in the adapter layer because it depends on SQLAlchemy internals.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, cast

from sqlalchemy import inspect
from sqlalchemy.orm import InstanceState
from sqlmodel import SQLModel


def compute_changes(
    row: SQLModel,
    fields: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Extract old→new changes from SQLAlchemy's attribute history.

    Must be called **after** mutating the ORM row but **before** ``session.flush()``,
    because ``flush()`` resets the attribute history.

    Args:
        row: A mapped SQLModel instance with pending (unflushed) mutations.
        fields: Optional list of field names to inspect. When ``None``, all
            mapper column attributes are inspected.

    Returns:
        A dict keyed by field name, each value being ``{"old": ..., "new": ...}``.
        Only fields that actually changed are included. An empty dict means no
        changes were detected.
    """
    state = cast(InstanceState[SQLModel], inspect(row))
    mapper = state.mapper

    if fields is None:
        fields = [attr.key for attr in mapper.column_attrs]

    changes: dict[str, dict[str, Any]] = {}
    for field in fields:
        history = state.attrs[field].history
        if not history.has_changes():
            continue

        old = history.deleted[0] if history.deleted else None
        new = history.added[0] if history.added else None
        changes[field] = {
            "old": _serialize(old),
            "new": _serialize(new),
        }

    return changes


def snapshot_new(
    row: SQLModel,
    fields: list[str] | None = None,
    *,
    exclude: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build a changes dict for a newly created row (old is always ``None``).

    Args:
        row: A mapped SQLModel instance that has been added to the session
            (but not necessarily flushed — ``id`` may still be ``None``).
        fields: Optional list of field names to include. When ``None``, all
            mapper column attributes are included.
        exclude: Optional set of field names to skip (e.g. ``{"id"}``).

    Returns:
        A dict keyed by field name, each value being ``{"old": None, "new": ...}``.
    """
    state = cast(InstanceState[SQLModel], inspect(row))
    mapper = state.mapper
    _exclude = exclude or set()

    if fields is None:
        fields = [attr.key for attr in mapper.column_attrs if attr.key not in _exclude]
    else:
        fields = [f for f in fields if f not in _exclude]

    changes: dict[str, dict[str, Any]] = {}
    for field in fields:
        value = getattr(row, field)
        if value is not None:
            changes[field] = {"old": None, "new": _serialize(value)}

    return changes


def _serialize(value: Any) -> Any:
    """Serialize a value for JSON storage in the audit log.

    Handles enums (→ ``.value``), Decimals (→ ``str``), dates and datetimes (→ ISO 8601)
    so the result is always JSON-serializable.
    """
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value
