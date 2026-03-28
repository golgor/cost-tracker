"""Contract tests for adapter round-trip mapping.

Verifies that domain models can be persisted and retrieved without data loss.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.adapters.sqlalchemy.group_adapter import SqlAlchemyGroupAdapter
from app.adapters.sqlalchemy.orm_models import MembershipRow, UserRow
from app.adapters.sqlalchemy.recurring_adapter import SqlAlchemyRecurringDefinitionAdapter
from app.adapters.sqlalchemy.user_adapter import SqlAlchemyUserAdapter
from app.domain.models import MemberRole, RecurringFrequency, SplitType


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
        assert user2.created_at == original_created
        assert user2.updated_at >= original_created

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
            "Home",
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

        created = adapter.save("Family")
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
        group = group_adapter.save("Apartment")
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
        group = group_adapter.save("Household")
        group_adapter.add_member(group.id, user.id, MemberRole.USER)
        db_session.commit()

        retrieved_group = group_adapter.get_by_user_id(user.id)

        assert retrieved_group is not None
        assert retrieved_group.id == group.id
        assert retrieved_group.name == "Household"

    def test_group_row_never_leaves_adapter(self, db_session: Session):
        """Group adapter returns GroupPublic, not GroupRow."""
        adapter = SqlAlchemyGroupAdapter(db_session)

        group = adapter.save("Boundary Group")
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
        group = group_adapter.save("Boundary Household")
        db_session.commit()

        membership = group_adapter.add_member(group.id, user.id, MemberRole.USER)
        db_session.commit()

        assert type(membership).__name__ == "MembershipPublic"
        assert not isinstance(membership, MembershipRow)


class TestRecurringDefinitionAdapterContract:
    """Contract tests for RecurringDefinition adapter round-trip mapping."""

    def _make_adapter(self, session: Session) -> SqlAlchemyRecurringDefinitionAdapter:
        return SqlAlchemyRecurringDefinitionAdapter(session)

    def _make_group_and_payer(self, session: Session):
        """Create a test group and user for use as payer_id/group_id."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(session, "auth0|contract_recurring", "recurring@example.com")
        group = create_test_group(session, user.id)
        return group, user

    def test_save_and_retrieve_by_id(self, db_session: Session):
        """RecurringDefinition can be saved and retrieved by ID with all fields preserved."""
        from app.domain.models import RecurringDefinitionPublic

        group, user = self._make_group_and_payer(db_session)
        adapter = self._make_adapter(db_session)

        defn = adapter.save(
            RecurringDefinitionPublic.model_construct(
                id=0,
                group_id=group.id,
                name="Netflix",
                amount=Decimal("14.99"),
                frequency=RecurringFrequency.MONTHLY,
                next_due_date=date(2026, 4, 1),
                payer_id=user.id,
                split_type=SplitType.EVEN,
                currency="EUR",
            ),
        )
        db_session.commit()

        retrieved = adapter.get_by_id(defn.id)

        assert retrieved is not None
        assert retrieved.id == defn.id
        assert retrieved.name == "Netflix"
        assert retrieved.amount == Decimal("14.99")
        assert retrieved.frequency == RecurringFrequency.MONTHLY
        assert retrieved.next_due_date == date(2026, 4, 1)
        assert retrieved.split_type == SplitType.EVEN
        assert retrieved.currency == "EUR"
        assert retrieved.deleted_at is None
        assert retrieved.created_at is not None
        assert retrieved.updated_at is not None

    def test_save_with_split_config_round_trip(self, db_session: Session):
        """split_config dict is persisted and retrieved without data loss."""
        from app.domain.models import RecurringDefinitionPublic

        group, user = self._make_group_and_payer(db_session)
        adapter = self._make_adapter(db_session)

        split_config = {"1": "60", "2": "40"}
        defn = adapter.save(
            RecurringDefinitionPublic.model_construct(
                id=0,
                group_id=group.id,
                name="Electricity",
                amount=Decimal("75.00"),
                frequency=RecurringFrequency.MONTHLY,
                next_due_date=date(2026, 4, 28),
                payer_id=user.id,
                split_type=SplitType.PERCENTAGE,
                split_config=split_config,
                currency="EUR",
            ),
        )
        db_session.commit()

        retrieved = adapter.get_by_id(defn.id)

        assert retrieved is not None
        assert retrieved.split_config == split_config

    def test_save_every_n_months_round_trip(self, db_session: Session):
        """EVERY_N_MONTHS frequency with interval_months is preserved."""
        from app.domain.models import RecurringDefinitionPublic

        group, user = self._make_group_and_payer(db_session)
        adapter = self._make_adapter(db_session)

        defn = adapter.save(
            RecurringDefinitionPublic.model_construct(
                id=0,
                group_id=group.id,
                name="Car Insurance",
                amount=Decimal("340.00"),
                frequency=RecurringFrequency.EVERY_N_MONTHS,
                interval_months=6,
                next_due_date=date(2026, 4, 15),
                payer_id=user.id,
                split_type=SplitType.EVEN,
                currency="EUR",
            ),
        )
        db_session.commit()

        retrieved = adapter.get_by_id(defn.id)

        assert retrieved is not None
        assert retrieved.frequency == RecurringFrequency.EVERY_N_MONTHS
        assert retrieved.interval_months == 6

    def test_soft_delete_sets_deleted_at(self, db_session: Session):
        """soft_delete() sets deleted_at; row is not removed from DB."""
        from app.domain.models import RecurringDefinitionPublic

        group, user = self._make_group_and_payer(db_session)
        adapter = self._make_adapter(db_session)

        defn = adapter.save(
            RecurringDefinitionPublic.model_construct(
                id=0,
                group_id=group.id,
                name="To Be Deleted",
                amount=Decimal("9.99"),
                frequency=RecurringFrequency.MONTHLY,
                next_due_date=date(2026, 4, 1),
                payer_id=user.id,
                split_type=SplitType.EVEN,
                currency="EUR",
            ),
        )
        db_session.commit()

        adapter.soft_delete(defn.id)
        db_session.commit()

        retrieved = adapter.get_by_id(defn.id)
        assert retrieved is not None
        assert retrieved.deleted_at is not None

    def test_row_never_leaves_adapter(self, db_session: Session):
        """adapter returns RecurringDefinitionPublic, not RecurringDefinitionRow."""
        from app.domain.models import RecurringDefinitionPublic

        group, user = self._make_group_and_payer(db_session)
        adapter = self._make_adapter(db_session)

        defn = adapter.save(
            RecurringDefinitionPublic.model_construct(
                id=0,
                group_id=group.id,
                name="Boundary Test",
                amount=Decimal("9.99"),
                frequency=RecurringFrequency.MONTHLY,
                next_due_date=date(2026, 4, 1),
                payer_id=user.id,
                split_type=SplitType.EVEN,
                currency="EUR",
            ),
        )
        db_session.commit()

        assert type(defn).__name__ == "RecurringDefinitionPublic"
