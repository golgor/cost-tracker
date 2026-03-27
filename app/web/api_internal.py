"""Internal API routes for system-to-system operations (cron, webhooks).

These endpoints are NOT protected by session auth — they use a shared secret
in the Authorization header instead. The path /api/internal/... is in
EXACT_PUBLIC_PATHS so AuthMiddleware and CSRFMiddleware skip them.
"""

import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlmodel import Session

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.dependencies import get_db_session
from app.domain.errors import DuplicateBillingPeriodError
from app.domain.use_cases.recurring import create_expense_from_definition
from app.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal", tags=["internal"])

DbSession = Annotated[Session, Depends(get_db_session)]


def _verify_webhook_secret(authorization: str | None) -> None:
    """Validate Authorization: Bearer <secret> header."""
    expected = f"Bearer {settings.INTERNAL_WEBHOOK_SECRET}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing webhook secret",
        )


def run_auto_generation(session: Session, current_date: date, actor_id: int) -> dict:
    """Create expenses for all overdue auto-generate definitions.

    Uses savepoints so a duplicate-billing-period error on one definition
    does not abort the others.

    Returns:
        {"created": int, "skipped": int, "errors": int}
    """
    uow = UnitOfWork(session)
    definitions = uow.recurring.list_overdue_auto(current_date)

    created_count = 0
    skipped_count = 0
    error_count = 0

    for defn in definitions:
        try:
            with session.begin_nested():
                create_expense_from_definition(uow, defn, actor_id=actor_id, is_auto_generated=True)
            created_count += 1
            logger.info(
                "Auto-generated expense for recurring definition %d (%s)",
                defn.id,
                defn.name,
            )
        except DuplicateBillingPeriodError:
            skipped_count += 1
            logger.debug(
                "Skipped definition %d (%s) — expense already exists for billing period %s",
                defn.id,
                defn.name,
                defn.next_due_date,
            )
        except Exception:
            error_count += 1
            logger.exception(
                "Unexpected error auto-generating expense for definition %d (%s)",
                defn.id,
                defn.name,
            )

    session.commit()

    return {"created": created_count, "skipped": skipped_count, "errors": error_count}


@router.post("/generate-recurring")
async def generate_recurring(
    session: DbSession,
    authorization: Annotated[str | None, Header()] = None,
):
    """Trigger auto-generation of recurring expenses.

    Called by external cron / scheduler. Requires Authorization: Bearer <secret>.
    """
    _verify_webhook_secret(authorization)

    result = run_auto_generation(session, date.today(), settings.SYSTEM_ACTOR_ID)

    logger.info(
        "Auto-generation complete: created=%d skipped=%d errors=%d",
        result["created"],
        result["skipped"],
        result["errors"],
    )

    return result
