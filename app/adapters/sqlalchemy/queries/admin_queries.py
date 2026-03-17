"""Read-only queries for admin interface."""

from sqlmodel import Session, select

from app.adapters.sqlalchemy.orm_models import UserRow
from app.domain.models import UserPublic


def get_all_users(session: Session) -> list[UserPublic]:
    """Fetch all users for admin display (read-only)."""
    statement = select(UserRow).order_by(UserRow.created_at.desc())
    rows = session.exec(statement).all()

    return [
        UserPublic(
            id=row.id,
            oidc_sub=row.oidc_sub,
            email=row.email,
            display_name=row.display_name,
            role=row.role,
            is_active=row.is_active,
            deactivated_at=row.deactivated_at,
            deactivated_by_user_id=row.deactivated_by_user_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


def get_recent_audit_entries(session: Session, limit: int = 50) -> list:
    """Fetch recent audit log entries (read-only)."""
    from sqlmodel import select

    from app.adapters.sqlalchemy.orm_models import AuditRow, UserRow

    statement = (
        select(AuditRow, UserRow)
        .join(UserRow, AuditRow.actor_id == UserRow.id, isouter=True)
        .order_by(AuditRow.occurred_at.desc())
        .limit(limit)
    )
    
    results = session.exec(statement).all()
    
    return [
        {
            "id": audit.id,
            "actor_name": user.display_name if user else "System",
            "action": audit.action,
            "target_type": audit.target_type,
            "target_id": audit.target_id,
            "old_value": audit.old_value,
            "new_value": audit.new_value,
            "occurred_at": audit.occurred_at,
        }
        for audit, user in results
    ]
