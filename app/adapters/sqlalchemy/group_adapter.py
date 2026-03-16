from datetime import datetime
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.adapters.sqlalchemy.orm_models import GroupRow, MembershipRow
from app.domain.models import (
    GroupPublic,
    MemberRole,
    MembershipPublic,
    SplitType,
)

UTC = ZoneInfo("UTC")


class SqlAlchemyGroupAdapter:
    """SQLAlchemy adapter implementing GroupPort."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, group_id: int) -> GroupPublic | None:
        """Retrieve group by database ID."""
        row = self._session.get(GroupRow, group_id)
        if row is None:
            return None
        return self._to_public(row)

    def get_by_user_id(self, user_id: int) -> GroupPublic | None:
        """Retrieve group that user belongs to (MVP1: single household)."""
        statement = (
            select(GroupRow)
            .join(MembershipRow)
            .where(MembershipRow.user_id == user_id)
        )
        row = self._session.exec(statement).first()
        if row is None:
            return None
        return self._to_public(row)

    def get_default_group(self) -> GroupPublic | None:
        """Get the default/only household group (MVP1: single household)."""
        statement = select(GroupRow).limit(1)
        row = self._session.exec(statement).first()
        if row is None:
            return None
        return self._to_public(row)

    def save(
        self,
        name: str,
        default_currency: str = "EUR",
        default_split_type: SplitType = SplitType.EVEN,
    ) -> GroupPublic:
        """Create a new group. Returns the persisted group."""
        row = GroupRow(
            name=name,
            default_currency=default_currency,
            default_split_type=default_split_type,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_public(row)

    def update(
        self,
        group_id: int,
        name: str | None = None,
        default_currency: str | None = None,
        default_split_type: SplitType | None = None,
    ) -> GroupPublic:
        """Update group configuration. Returns the updated group."""
        row = self._session.get(GroupRow, group_id)
        if row is None:
            raise ValueError(f"Group {group_id} not found")

        if name is not None:
            row.name = name
        if default_currency is not None:
            row.default_currency = default_currency
        if default_split_type is not None:
            row.default_split_type = default_split_type

        row.updated_at = datetime.now(UTC)
        self._session.add(row)
        self._session.flush()
        return self._to_public(row)

    def add_member(self, group_id: int, user_id: int, role: MemberRole) -> MembershipPublic:
        """Add a user to a group with specified role."""
        membership = MembershipRow(
            user_id=user_id,
            group_id=group_id,
            role=role,
        )
        self._session.add(membership)
        self._session.flush()
        return self._to_membership_public(membership)

    def get_membership(self, user_id: int, group_id: int) -> MembershipPublic | None:
        """Get membership for a specific user and group."""
        statement = select(MembershipRow).where(
            MembershipRow.user_id == user_id,
            MembershipRow.group_id == group_id,
        )
        row = self._session.exec(statement).first()
        if row is None:
            return None
        return self._to_membership_public(row)

    def has_active_admin(self) -> bool:
        """Check if any active admin exists in the system (admin bootstrap trigger)."""
        statement = select(MembershipRow).where(MembershipRow.role == MemberRole.ADMIN).limit(1)
        row = self._session.exec(statement).first()
        return row is not None

    def _to_public(self, row: GroupRow) -> GroupPublic:
        """Convert ORM row to public domain model. Row never leaves adapter."""
        return GroupPublic(
            id=row.id,  # type: ignore[arg-type]
            name=row.name,
            default_currency=row.default_currency,
            default_split_type=row.default_split_type,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _to_membership_public(self, row: MembershipRow) -> MembershipPublic:
        """Convert ORM row to public domain model. Row never leaves adapter."""
        return MembershipPublic(
            user_id=row.user_id,
            group_id=row.group_id,
            role=row.role,
            joined_at=row.joined_at,
        )
