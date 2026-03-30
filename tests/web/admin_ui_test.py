"""Tests for admin UI interface (user list page)."""

import pytest
from starlette.testclient import TestClient

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.auth.session import encode_session
from app.dependencies import get_uow
from app.main import app


@pytest.fixture
def test_user(uow: UnitOfWork):
    """Create a test user."""
    with uow:
        user = uow.users.save(
            oidc_sub="user@test.com",
            email="user@test.com",
            display_name="Test User",
        )
    return user


@pytest.fixture
def authenticated_client(test_user, uow):
    """Test client with session cookie for authenticated user."""
    app.dependency_overrides[get_uow] = lambda: uow

    client = TestClient(app, raise_server_exceptions=False)
    session_token = encode_session(test_user.id)
    client.cookies.set("cost_tracker_session", session_token)

    yield client
    app.dependency_overrides.clear()


class TestAdminUsersPage:
    """Test admin users page access."""

    def test_admin_users_page_returns_200(self, authenticated_client: TestClient):
        """Authenticated user can access /admin/users."""
        response = authenticated_client.get("/admin/users")
        assert response.status_code == 200
        assert "User Management" in response.text or "Admin" in response.text


class TestProfileDropdown:
    """Test profile dropdown rendering."""

    def test_profile_dropdown_structure(self, authenticated_client: TestClient, test_user):
        """Profile dropdown has correct structure: name and logout."""
        response = authenticated_client.get("/expenses")
        html = response.text

        # Check user name appears
        assert test_user.display_name in html
        # Check logout link exists
        assert "/auth/logout" in html


class TestUserRowViewModel:
    """Unit tests for UserRowViewModel presentation logic."""

    def test_user_row_view_model(self, test_user):
        """User has correct display fields."""
        from app.web.view_models import UserRowViewModel

        vm = UserRowViewModel.from_domain(test_user)

        assert vm.id == test_user.id
        assert vm.display_name == test_user.display_name
        assert vm.email == test_user.email


class TestUserProfileViewModel:
    """Unit tests for UserProfileViewModel presentation logic."""

    def test_profile_view_model(self, test_user):
        """Profile has correct display fields."""
        from app.web.view_models import UserProfileViewModel

        vm = UserProfileViewModel.from_domain(test_user)

        assert vm.display_name == test_user.display_name
        assert vm.email == test_user.email
        assert vm.avatar_initial == test_user.display_name[0].upper()
        # Check member_since format (e.g., "March 18, 2026")
        assert len(vm.member_since) > 0
        assert "," in vm.member_since  # Date format includes comma
