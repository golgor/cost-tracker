"""Read-only queries module."""

from app.adapters.sqlalchemy.queries.admin_queries import (
    get_all_users,
)

__all__ = ["get_all_users"]
