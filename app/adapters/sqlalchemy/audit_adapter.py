from typing import Any

from sqlmodel import Session

from app.adapters.sqlalchemy.orm_models import AuditRow
from app.domain.models import AuditEntry


class SqlAlchemyAuditAdapter:
    """SQLAlchemy adapter implementing AuditPort."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def log(
        self,
        *,
        action: str,
        actor_id: int,
        entity_type: str,
        entity_id: int,
        changes: dict[str, Any] | None = None,
    ) -> None:
        """Persist an audit log entry. Shares the same session/transaction as business changes."""
        row = AuditRow(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            changes=changes,
        )
        self._session.add(row)
        self._session.flush()

    def _to_public(self, row: AuditRow) -> AuditEntry:
        """Convert ORM row to public domain model. Row never leaves adapter."""
        assert row.id is not None  # guaranteed for persisted rows
        return AuditEntry(
            id=row.id,
            actor_id=row.actor_id,
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            occurred_at=row.occurred_at,
            changes=row.changes,
        )
