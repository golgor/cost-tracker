from datetime import UTC

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.adapters.sqlalchemy.orm_models import UserRow
from app.domain.errors import (
    UserAlreadyActive,
    UserAlreadyAdminError,
    UserAlreadyDeactivated,
    UserAlreadyRegularError,
    UserNotFoundError,
)
from app.domain.models import UserPublic, UserRole


class SqlAlchemyUserAdapter:
    """SQLAlchemy adapter implementing UserPort."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: int) -> UserPublic | None:
        """Retrieve user by database ID."""
        row = self._session.get(UserRow, user_id)
        if row is None:
            return None
        return self._to_public(row)

    def get_by_ids(self, user_ids: list[int]) -> list[UserPublic]:
        """Retrieve multiple users by their database IDs."""
        if not user_ids:
            return []
        statement = select(UserRow).where(UserRow.id.in_(user_ids))
        rows = self._session.exec(statement).all()
        return [self._to_public(row) for row in rows]

    def get_by_oidc_sub(self, oidc_sub: str) -> UserPublic | None:
        """Retrieve user by OIDC subject identifier."""
        statement = select(UserRow).where(UserRow.oidc_sub == oidc_sub)
        row = self._session.exec(statement).first()
        if row is None:
            return None
        return self._to_public(row)

    def save(self, oidc_sub: str, email: str, display_name: str) -> UserPublic:
        """Create or update a user. Returns the persisted user."""
        existing = self._session.exec(select(UserRow).where(UserRow.oidc_sub == oidc_sub)).first()

        if existing:
            existing.email = email
            existing.display_name = display_name
            self._session.add(existing)
            self._session.flush()
            return self._to_public(existing)

        row = UserRow(
            oidc_sub=oidc_sub,
            email=email,
            display_name=display_name,
        )
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
            self._session.add(existing)
            self._session.flush()
            return self._to_public(existing)

        return self._to_public(row)

    def promote_to_admin(self, user_id: int) -> UserPublic:
        """Promote user to admin role."""
        row = self._session.get(UserRow, user_id)
        if row is None:
            raise UserNotFoundError(f"User {user_id} not found")

        if row.role == UserRole.ADMIN:
            raise UserAlreadyAdminError(f"User {user_id} is already an admin")

        row.role = UserRole.ADMIN
        self._session.add(row)
        self._session.flush()

        return self._to_public(row)

    def demote_to_user(self, user_id: int) -> UserPublic:
        """Demote user to regular user role."""
        row = self._session.get(UserRow, user_id)
        if row is None:
            raise UserNotFoundError(f"User {user_id} not found")

        if row.role == UserRole.USER:
            raise UserAlreadyRegularError(f"User {user_id} is already a regular user")

        row.role = UserRole.USER
        self._session.add(row)
        self._session.flush()

        return self._to_public(row)

    def deactivate(self, user_id: int) -> UserPublic:
        """Deactivate a user."""
        row = self._session.get(UserRow, user_id)
        if row is None:
            raise UserNotFoundError(f"User {user_id} not found")

        if not row.is_active:
            raise UserAlreadyDeactivated(f"User {user_id} is already deactivated")

        from datetime import datetime

        row.is_active = False
        row.deactivated_at = datetime.now(UTC)
        row.deactivated_by_user_id = None

        self._session.add(row)
        self._session.flush()

        return self._to_public(row)

    def reactivate(self, user_id: int) -> UserPublic:
        """Reactivate a deactivated user."""
        row = self._session.get(UserRow, user_id)
        if row is None:
            raise UserNotFoundError(f"User {user_id} not found")

        if row.is_active:
            raise UserAlreadyActive(f"User {user_id} is already active")

        row.is_active = True
        row.deactivated_at = None
        row.deactivated_by_user_id = None

        self._session.add(row)
        self._session.flush()

        return self._to_public(row)

    def count_active_admins(self) -> int:
        """Count the number of active admin users."""
        from sqlalchemy import func

        statement = (
            select(func.count())
            .select_from(UserRow)
            .where((UserRow.role == UserRole.ADMIN) & (UserRow.is_active == True))  # noqa: E712
        )
        result = self._session.exec(statement).first()
        return result or 0

    def get_active_admins(self) -> list[UserPublic]:
        """Get list of all active admin users."""
        statement = select(UserRow).where(
            (UserRow.role == UserRole.ADMIN) & (UserRow.is_active == True)  # noqa: E712
        )
        rows = self._session.exec(statement).all()
        return [self._to_public(row) for row in rows]

    def _to_public(self, row: UserRow) -> UserPublic:
        """Convert ORM row to public domain model. Row never leaves adapter."""
        if row.id is None:
            raise RuntimeError("Row ID must not be None for persisted rows")
        return UserPublic(
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
