"""Contract tests for adapter round-trip mapping.

Verifies that domain models can be persisted and retrieved without data loss.
"""

import pytest
from sqlalchemy.orm import Session

from app.adapters.sqlalchemy.orm_models import UserRow
from app.adapters.sqlalchemy.user_adapter import SqlAlchemyUserAdapter


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
