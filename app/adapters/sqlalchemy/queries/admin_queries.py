"""Read-only queries for admin interface."""

from sqlmodel import Session, select

from app.adapters.sqlalchemy.orm_models import UserRow
from app.domain.models import UserPublic


def get_all_users(session: Session) -> list[UserPublic]:
    """Fetch all users for admin display (read-only)."""
    statement = select(UserRow).order_by(UserRow.created_at.desc())  # type: ignore[attr-defined]
    rows = session.exec(statement).all()

    return [
        UserPublic(
            id=row.id,  # ty: ignore[invalid-argument-type]  # guaranteed non-None for persisted rows
            oidc_sub=row.oidc_sub,
            email=row.email,
            display_name=row.display_name,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
