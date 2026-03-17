"""Read-only queries module."""

from app.adapters.sqlalchemy.queries.admin_queries import (
    get_all_users,
    get_recent_audit_entries,
)

__all__ = ["get_all_users", "get_recent_audit_entries"]
