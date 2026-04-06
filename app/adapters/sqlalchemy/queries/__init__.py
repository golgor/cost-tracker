"""Read-only queries module."""

from app.adapters.sqlalchemy.queries.dashboard_queries import (
    get_all_users,
)

__all__ = ["get_all_users"]
