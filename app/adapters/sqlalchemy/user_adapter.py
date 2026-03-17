from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.adapters.sqlalchemy.audit_adapter import SqlAlchemyAuditAdapter
from app.adapters.sqlalchemy.changes import compute_changes, snapshot_new
from app.adapters.sqlalchemy.orm_models import UserRow
from app.domain.models import UserPublic


class SqlAlchemyUserAdapter:
    """SQLAlchemy adapter implementing UserPort."""

    def __init__(self, session: Session, audit: SqlAlchemyAuditAdapter) -> None:
        self._session = session
        self._audit = audit

    def get_by_id(self, user_id: int) -> UserPublic | None:
        """Retrieve user by database ID."""
        row = self._session.get(UserRow, user_id)
        if row is None:
            return None
        return self._to_public(row)

    def get_by_oidc_sub(self, oidc_sub: str) -> UserPublic | None:
        """Retrieve user by OIDC subject identifier."""
        statement = select(UserRow).where(UserRow.oidc_sub == oidc_sub)
        row = self._session.exec(statement).first()
        if row is None:
            return None
        return self._to_public(row)

    def save(self, oidc_sub: str, email: str, display_name: str) -> UserPublic:
        """Create or update a user. Returns the persisted user. Auto-audits.

        TODO(1.6): Refactor to accept `actor_id` as keyword parameter like other
        adapters (GroupAdapter). Currently self-audits with actor_id=user's own ID
        because there is no provision_user use case to provide actor context.
        Story 1.6 will introduce the use case with role assignment and deactivation
        checks — at that point, remove self-auditing here and let the use case pass
        actor_id through. See: 1-6-admin-bootstrap-and-user-lifecycle-core.md
        """
        existing = self._session.exec(select(UserRow).where(UserRow.oidc_sub == oidc_sub)).first()

        if existing:
            existing.email = email
            existing.display_name = display_name
            changes = compute_changes(existing)
            self._session.add(existing)
            self._session.flush()
            if changes:
                self._audit.log(
                    action="user_updated",
                    actor_id=existing.id,
                    entity_type="user",
                    entity_id=existing.id,
                    changes=changes,
                )
            return self._to_public(existing)

        row = UserRow(
            oidc_sub=oidc_sub,
            email=email,
            display_name=display_name,
        )
        changes = snapshot_new(row, exclude={"id", "created_at", "updated_at"})
        self._session.add(row)
        try:
            self._session.flush()
        except IntegrityError:
            # Race condition: a concurrent request inserted the same oidc_sub.
            # Roll back to a clean state and update the existing row instead.
            self._session.rollback()
            existing = self._session.exec(select(UserRow).where(UserRow.oidc_sub == oidc_sub)).one()
            existing.email = email
            existing.display_name = display_name
            changes = compute_changes(existing)
            self._session.add(existing)
            self._session.flush()
            if changes:
                self._audit.log(
                    action="user_updated",
                    actor_id=existing.id,
                    entity_type="user",
                    entity_id=existing.id,
                    changes=changes,
                )
            return self._to_public(existing)

        self._audit.log(
            action="user_created",
            actor_id=row.id,
            entity_type="user",
            entity_id=row.id,
            changes=changes,
        )
        return self._to_public(row)

    def _to_public(self, row: UserRow) -> UserPublic:
        """Convert ORM row to public domain model. Row never leaves adapter."""
        return UserPublic(
            id=row.id,  # type: ignore[arg-type]
            oidc_sub=row.oidc_sub,
            email=row.email,
            display_name=row.display_name,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
