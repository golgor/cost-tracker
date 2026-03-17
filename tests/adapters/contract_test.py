"""Contract tests for adapter round-trip mapping.

Verifies that domain models can be persisted and retrieved without data loss.
"""

from sqlalchemy.orm import Session

from app.adapters.sqlalchemy.group_adapter import SqlAlchemyGroupAdapter
from app.adapters.sqlalchemy.orm_models import MembershipRow, UserRow
from app.adapters.sqlalchemy.user_adapter import SqlAlchemyUserAdapter
from app.domain.models import MemberRole, SplitType


class TestUserAdapterContract:
    """Contract tests for User adapter round-trip mapping."""

    def test_save_and_retrieve_by_id(self, db_session: Session):
        """User can be saved and retrieved by ID."""
        adapter = SqlAlchemyUserAdapter(db_session)

        # Save a new user
        user = adapter.save(
            oidc_sub="auth0|12345",
            email="test@example.com",
            display_name="Test User",
        )
        db_session.commit()

        # Retrieve by ID
        retrieved = adapter.get_by_id(user.id)

        assert retrieved is not None
        assert retrieved.id == user.id
        assert retrieved.oidc_sub == "auth0|12345"
        assert retrieved.email == "test@example.com"
        assert retrieved.display_name == "Test User"
        assert retrieved.created_at is not None
        assert retrieved.updated_at is not None

    def test_save_and_retrieve_by_oidc_sub(self, db_session: Session):
        """User can be retrieved by OIDC subject identifier."""
        adapter = SqlAlchemyUserAdapter(db_session)

        user = adapter.save(
            oidc_sub="auth0|67890",
            email="another@example.com",
            display_name="Another User",
        )
        db_session.commit()

        # Retrieve by OIDC sub
        retrieved = adapter.get_by_oidc_sub("auth0|67890")

        assert retrieved is not None
        assert retrieved.id == user.id
        assert retrieved.oidc_sub == "auth0|67890"

    def test_save_updates_existing_user(self, db_session: Session):
        """Saving with existing OIDC sub updates the user."""
        adapter = SqlAlchemyUserAdapter(db_session)

        # Create initial user
        user1 = adapter.save(
            oidc_sub="auth0|update_test",
            email="old@example.com",
            display_name="Old Name",
        )
        db_session.commit()
        original_id = user1.id
        original_created = user1.created_at

        # Update the same user
        user2 = adapter.save(
            oidc_sub="auth0|update_test",
            email="new@example.com",
            display_name="New Name",
        )
        db_session.commit()

        # Should be the same user
        assert user2.id == original_id
        assert user2.email == "new@example.com"
        assert user2.display_name == "New Name"
        # Compare without timezone info (SQLite doesn't preserve it)
        assert user2.created_at.replace(tzinfo=None) == original_created.replace(tzinfo=None)
        assert user2.updated_at.replace(tzinfo=None) >= original_created.replace(tzinfo=None)

    def test_get_by_id_returns_none_for_missing(self, db_session: Session):
        """get_by_id returns None for non-existent ID."""
        adapter = SqlAlchemyUserAdapter(db_session)
        assert adapter.get_by_id(99999) is None

    def test_get_by_oidc_sub_returns_none_for_missing(self, db_session: Session):
        """get_by_oidc_sub returns None for non-existent OIDC sub."""
        adapter = SqlAlchemyUserAdapter(db_session)
        assert adapter.get_by_oidc_sub("nonexistent") is None

    def test_user_row_never_leaves_adapter(self, db_session: Session):
        """Adapter returns UserPublic, not UserRow."""
        adapter = SqlAlchemyUserAdapter(db_session)

        user = adapter.save(
            oidc_sub="auth0|boundary_test",
            email="boundary@example.com",
            display_name="Boundary Test",
        )
        db_session.commit()

        retrieved = adapter.get_by_id(user.id)

        # Should be UserPublic, not UserRow
        assert type(retrieved).__name__ == "UserPublic"
        assert not isinstance(retrieved, UserRow)


class TestGroupAdapterContract:
    """Contract tests for Group adapter round-trip mapping."""

    def test_save_and_retrieve_group_by_id(self, db_session: Session):
        """Group can be saved and retrieved by ID with all fields preserved."""
        adapter = SqlAlchemyGroupAdapter(db_session)

        group = adapter.save(
            name="Home",
            default_currency="EUR",
            default_split_type=SplitType.EVEN,
            tracking_threshold=45,
        )
        db_session.commit()

        retrieved = adapter.get_by_id(group.id)

        assert retrieved is not None
        assert retrieved.id == group.id
        assert retrieved.name == "Home"
        assert retrieved.default_currency == "EUR"
        assert retrieved.default_split_type == SplitType.EVEN
        assert retrieved.tracking_threshold == 45
        assert retrieved.created_at is not None
        assert retrieved.updated_at is not None

    def test_get_default_group_returns_singleton_group(self, db_session: Session):
        """Default group returns the first/only persisted household group."""
        adapter = SqlAlchemyGroupAdapter(db_session)

        created = adapter.save(name="Family")
        db_session.commit()

        default_group = adapter.get_default_group()

        assert default_group is not None
        assert default_group.id == created.id
        assert default_group.name == "Family"

    def test_add_member_and_get_membership_round_trip(self, db_session: Session):
        """Membership can be added and retrieved with role/joined_at preserved."""
        user_adapter = SqlAlchemyUserAdapter(db_session)
        group_adapter = SqlAlchemyGroupAdapter(db_session)

        user = user_adapter.save(
            oidc_sub="auth0|member_contract",
            email="member@example.com",
            display_name="Member User",
        )
        group = group_adapter.save(name="Apartment")
        db_session.commit()

        membership = group_adapter.add_member(group.id, user.id, MemberRole.ADMIN)
        db_session.commit()

        retrieved = group_adapter.get_membership(user.id, group.id)

        assert retrieved is not None
        assert membership.user_id == user.id
        assert membership.group_id == group.id
        assert membership.role == MemberRole.ADMIN
        assert membership.joined_at is not None
        assert retrieved.user_id == user.id
        assert retrieved.group_id == group.id
        assert retrieved.role == MemberRole.ADMIN
        assert retrieved.joined_at is not None

    def test_get_by_user_id_returns_users_group(self, db_session: Session):
        """Group can be resolved from user membership."""
        user_adapter = SqlAlchemyUserAdapter(db_session)
        group_adapter = SqlAlchemyGroupAdapter(db_session)

        user = user_adapter.save(
            oidc_sub="auth0|lookup_by_user",
            email="lookup@example.com",
            display_name="Lookup User",
        )
        group = group_adapter.save(name="Household")
        group_adapter.add_member(group.id, user.id, MemberRole.USER)
        db_session.commit()

        retrieved_group = group_adapter.get_by_user_id(user.id)

        assert retrieved_group is not None
        assert retrieved_group.id == group.id
        assert retrieved_group.name == "Household"

    def test_group_row_never_leaves_adapter(self, db_session: Session):
        """Group adapter returns GroupPublic, not GroupRow."""
        adapter = SqlAlchemyGroupAdapter(db_session)

        group = adapter.save(name="Boundary Group")
        db_session.commit()

        retrieved = adapter.get_by_id(group.id)

        assert retrieved is not None
        assert type(retrieved).__name__ == "GroupPublic"

    def test_membership_row_never_leaves_adapter(self, db_session: Session):
        """Membership adapter method returns MembershipPublic, not MembershipRow."""
        user_adapter = SqlAlchemyUserAdapter(db_session)
        group_adapter = SqlAlchemyGroupAdapter(db_session)

        user = user_adapter.save(
            oidc_sub="auth0|membership_boundary",
            email="membership-boundary@example.com",
            display_name="Membership Boundary",
        )
        group = group_adapter.save(name="Boundary Household")
        db_session.commit()

        membership = group_adapter.add_member(group.id, user.id, MemberRole.USER)
        db_session.commit()

        assert type(membership).__name__ == "MembershipPublic"
        assert not isinstance(membership, MembershipRow)
