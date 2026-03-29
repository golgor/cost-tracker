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
    """Test admin users page."""

    def test_admin_users_page_renders(self, authenticated_client: TestClient):
        """Admin users page renders successfully."""
        response = authenticated_client.get("/admin/users")
        assert response.status_code == 200
        assert "Users" in response.text

    def test_admin_users_page_shows_user(self, authenticated_client: TestClient):
        """Admin users page shows the authenticated user."""
        response = authenticated_client.get("/admin/users")
        assert response.status_code == 200
        assert "Test User" in response.text
        assert "user@test.com" in response.text


class TestUserRowViewModel:
    """Unit tests for UserRowViewModel presentation logic."""

    def test_user_row_view_model(self, test_user):
        """User row has correct display fields."""
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
        assert len(vm.member_since) > 0
        assert "," in vm.member_since
