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

    entries = []
    for audit, user in results:
        entry = {
            "id": audit.id,
            "actor_name": user.display_name if user else "System",
            "action": audit.action,
            "target_type": audit.entity_type,
            "target_id": audit.entity_id,
            "occurred_at": audit.occurred_at,
            "old_value": None,
            "new_value": None,
        }

        # Extract old/new values from changes dict if present
        if audit.changes:
            # For simple value changes, extract readable format
            if len(audit.changes) == 1:
                field, values = next(iter(audit.changes.items()))
                if isinstance(values, dict) and "old" in values and "new" in values:
                    entry["old_value"] = f"{field}: {values['old']}"
                    entry["new_value"] = f"{field}: {values['new']}"

        entries.append(entry)

    return entries
