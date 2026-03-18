"""Integration tests for admin mutations - verify transactions commit to database.

These tests validate that admin endpoints persist changes via use cases and UnitOfWork.
Tests use the use case layer directly to bypass CSRF middleware and test the core issue:
transaction commit behavior when with uow: context manager is used properly.
"""

import pytest

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.domain.models import UserRole
from app.domain.use_cases import users as user_use_cases


@pytest.fixture
def admin_user(uow: UnitOfWork):
    """Create an admin user."""
    with uow:
        user = uow.users.save(
            oidc_sub="admin@test.com",
            email="admin@test.com",
            display_name="Admin User",
            actor_id=1,
        )
        admin = uow.users.promote_to_admin(user.id, actor_id=user.id)
    return admin


@pytest.fixture
def regular_user(uow: UnitOfWork):
    """Create a regular user."""
    with uow:
        user = uow.users.save(
            oidc_sub="user@test.com",
            email="user@test.com",
            display_name="Regular User",
            actor_id=2,
        )
    return user


class TestPromoteUserPersistence:
    """Verify promote use case persists to database (transaction commit)."""

    def test_promote_persists_to_database(self, regular_user, admin_user, uow: UnitOfWork):
        """Promoting user persists role change to database."""
        # Verify regular user before
        user_before = uow.users.get_by_id(regular_user.id)
        assert user_before.role == UserRole.USER

        # Call use case within context manager (simulating endpoint behavior)
        with uow:
            user_use_cases.promote_user_to_admin(uow, regular_user.id, actor_id=admin_user.id)

        # Fresh lookup to verify persisted
        user_after = uow.users.get_by_id(regular_user.id)
        assert user_after.role == UserRole.ADMIN


class TestDemoteUserPersistence:
    """Verify demote use case persists to database."""

    def test_demote_persists_to_database(self, admin_user, uow: UnitOfWork):
        """Demoting admin persists role change to database."""
        # Create second admin to demote (can't demote last admin)
        with uow:
            second_admin = uow.users.save(
                oidc_sub="admin2@test.com",
                email="admin2@test.com",
                display_name="Second Admin",
                actor_id=99,
            )
            second_admin = uow.users.promote_to_admin(second_admin.id, actor_id=second_admin.id)

        # Verify admin before
        user_before = uow.users.get_by_id(second_admin.id)
        assert user_before.role == UserRole.ADMIN

        # Call demote
        with uow:
            user_use_cases.demote_user_to_regular(uow, second_admin.id, actor_id=admin_user.id)

        # Verify persisted to regular
        user_after = uow.users.get_by_id(second_admin.id)
        assert user_after.role == UserRole.USER


class TestDeactivateUserPersistence:
    """Verify deactivate use case persists to database."""

    def test_deactivate_persists_to_database(self, regular_user, admin_user, uow: UnitOfWork):
        """Deactivating user persists is_active=False to database."""
        # Verify active before
        user_before = uow.users.get_by_id(regular_user.id)
        assert user_before.is_active is True

        # Call deactivate
        with uow:
            user_use_cases.deactivate_user(uow, regular_user.id, actor_id=admin_user.id)

        # Verify persisted as inactive
        user_after = uow.users.get_by_id(regular_user.id)
        assert user_after.is_active is False


class TestReactivateUserPersistence:
    """Verify reactivate use case persists to database."""

    def test_reactivate_persists_to_database(self, regular_user, admin_user, uow: UnitOfWork):
        """Reactivating user persists is_active=True to database."""
        # First deactivate
        with uow:
            uow.users.deactivate(regular_user.id, actor_id=admin_user.id)

        # Verify inactive
        user_inactive = uow.users.get_by_id(regular_user.id)
        assert user_inactive.is_active is False

        # Call reactivate
        with uow:
            user_use_cases.reactivate_user(uow, regular_user.id, actor_id=admin_user.id)

        # Verify persisted as active
        user_after = uow.users.get_by_id(regular_user.id)
        assert user_after.is_active is True
