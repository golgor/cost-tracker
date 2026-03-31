"""Dev-mode authentication bypass utilities.

This module is only active when DEV_BYPASS_AUTH=True in settings. It must
never be imported conditionally — the guard is inside each function. This
keeps the import graph clean and avoids accidental activation.

Usage
-----
Call ``ensure_dev_user(session)`` once at application startup (lifespan).
The middleware then reads the cached ID via ``get_dev_user_id()`` on every
request — no DB query needed per request.

    NEVER set DEV_BYPASS_AUTH=True in production.
"""

import structlog
from sqlmodel import Session

from app.adapters.sqlalchemy.user_adapter import SqlAlchemyUserAdapter

logger = structlog.get_logger()

# Fixed identifiers for the synthetic dev user. Stable across restarts so the
# same DB row is always reused (upsert logic in SqlAlchemyUserAdapter).
DEV_USER_OIDC_SUB = "dev@localhost"
DEV_USER_EMAIL = "dev@localhost"
DEV_USER_DISPLAY_NAME = "Dev User"

# Module-level cache populated by ensure_dev_user() at startup.
# None means ensure_dev_user() has not been called yet.
_dev_user_id: int | None = None


def ensure_dev_user(session: Session) -> int:
    """Upsert the synthetic dev user and cache their database ID.

    Called once during application startup when DEV_BYPASS_AUTH=True.
    Creates the dev user if they do not exist, or updates the existing row
    if they do. The returned ID is stored in a module-level cache so the
    auth middleware can inject it without a DB query on every request.

    The caller is responsible for committing the session after this call.

    Args:
        session: An open database session. Must be committed by the caller.

    Returns:
        The database ID of the dev bypass user.
    """
    global _dev_user_id

    adapter = SqlAlchemyUserAdapter(session)
    user = adapter.save(
        oidc_sub=DEV_USER_OIDC_SUB,
        email=DEV_USER_EMAIL,
        display_name=DEV_USER_DISPLAY_NAME,
    )
    _dev_user_id = user.id

    logger.warning(
        "dev_bypass_auth_enabled",
        user_id=_dev_user_id,
        display_name=DEV_USER_DISPLAY_NAME,
        warning="Authentication is DISABLED. Never set DEV_BYPASS_AUTH=True in production.",
    )

    return _dev_user_id


def get_dev_user_id() -> int | None:
    """Return the cached dev user ID.

    Returns None if ``ensure_dev_user()`` has not been called yet (e.g. in
    tests that do not go through the full application lifespan). The auth
    middleware treats None as "bypass not ready" and falls through to normal
    auth, preventing silent failures on misconfiguration.
    """
    return _dev_user_id
