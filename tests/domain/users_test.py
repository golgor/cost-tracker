"""Tests for user lifecycle use cases."""

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.domain.use_cases import users as user_use_cases


class TestProvisionUser:
    """Test user provisioning via OIDC."""

    def test_provision_creates_new_user(self, uow: UnitOfWork):
        """New OIDC user is created on first login."""
        with uow:
            user = user_use_cases.provision_user(
                uow,
                oidc_sub="new_user_sub",
                email="new@example.com",
                display_name="New User",
            )

        assert user.id is not None
        assert user.oidc_sub == "new_user_sub"
        assert user.email == "new@example.com"
        assert user.display_name == "New User"

    def test_provision_updates_existing_user(self, uow: UnitOfWork):
        """Existing OIDC user gets updated on subsequent login."""
        with uow:
            user_use_cases.provision_user(
                uow,
                oidc_sub="existing_sub",
                email="old@example.com",
                display_name="Old Name",
            )

        with uow:
            user = user_use_cases.provision_user(
                uow,
                oidc_sub="existing_sub",
                email="new@example.com",
                display_name="New Name",
            )

        assert user.email == "new@example.com"
        assert user.display_name == "New Name"


class TestUserCount:
    """Test user count functionality."""

    def test_count_returns_zero_initially(self, uow: UnitOfWork):
        """No users initially."""
        assert uow.users.count() == 0

    def test_count_increments_after_provision(self, uow: UnitOfWork):
        """Count increases after provisioning users."""
        with uow:
            user_use_cases.provision_user(
                uow, oidc_sub="u1", email="u1@example.com", display_name="User 1"
            )

        assert uow.users.count() == 1

        with uow:
            user_use_cases.provision_user(
                uow, oidc_sub="u2", email="u2@example.com", display_name="User 2"
            )

        assert uow.users.count() == 2


class TestGetAllUsers:
    """Test get_all users functionality."""

    def test_get_all_returns_empty_initially(self, uow: UnitOfWork):
        """No users initially."""
        assert uow.users.get_all() == []

    def test_get_all_returns_all_users(self, uow: UnitOfWork):
        """Returns all provisioned users."""
        with uow:
            user_use_cases.provision_user(
                uow, oidc_sub="u1", email="u1@example.com", display_name="User 1"
            )
            user_use_cases.provision_user(
                uow, oidc_sub="u2", email="u2@example.com", display_name="User 2"
            )

        all_users = uow.users.get_all()
        assert len(all_users) == 2
