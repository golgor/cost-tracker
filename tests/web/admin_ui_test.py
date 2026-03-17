"""Tests for admin UI interface (profile dropdown, user management, audit log)."""

import pytest
from starlette.testclient import TestClient

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.auth.session import encode_session
from app.dependencies import get_uow
from app.main import app


@pytest.fixture
def admin_user(uow: UnitOfWork):
    """Create an admin user for testing."""
    user = uow.users.save(
        oidc_sub="admin@test.com",
        email="admin@test.com",
        display_name="Admin User",
        actor_id=1,
    )
    # Promote to admin
    admin = uow.users.promote_to_admin(user.id, actor_id=user.id)
    uow.commit()
    return admin


@pytest.fixture
def regular_user(uow: UnitOfWork):
    """Create a regular (non-admin) user for testing."""
    user = uow.users.save(
        oidc_sub="user@test.com",
        email="user@test.com",
        display_name="Regular User",
        actor_id=2,
    )
    uow.commit()
    return user


@pytest.fixture
def authenticated_client(admin_user, uow):
    """Test client with session cookie for authenticated admin user."""
    # Override get_uow to use test session
    app.dependency_overrides[get_uow] = lambda: uow

    client = TestClient(app, raise_server_exceptions=False)
    # Set session cookie
    session_token = encode_session(admin_user.id)
    client.cookies.set("cost_tracker_session", session_token)

    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def regular_client(regular_user, uow):
    """Test client with session cookie for authenticated regular user."""
    # Override get_uow to use test session
    app.dependency_overrides[get_uow] = lambda: uow

    client = TestClient(app, raise_server_exceptions=False)
    # Set session cookie
    session_token = encode_session(regular_user.id)
    client.cookies.set("cost_tracker_session", session_token)

    yield client
    app.dependency_overrides.clear()


class TestProfileDropdownAdminMenuItem:
    """Test profile dropdown shows/hides admin menu item based on role."""

    def test_admin_user_sees_admin_menu_item_desktop(
        self, authenticated_client: TestClient
    ):
        """Admin users see 'Admin' menu item in desktop profile dropdown."""
        response = authenticated_client.get("/")
        assert response.status_code == 200

        html = response.text
        # Check for admin link in dropdown
        assert 'href="/admin/users"' in html
        # Check the text "Admin" appears in the navigation area
        assert ">Admin<" in html or "Admin" in html

    def test_regular_user_does_not_see_admin_menu_item_desktop(
        self, regular_client: TestClient
    ):
        """Regular users do not see 'Admin' menu item."""
        response = regular_client.get("/")
        assert response.status_code == 200

        html = response.text
        # Admin link should not be present
        assert 'href="/admin/users"' not in html

    def test_profile_dropdown_structure_for_admin(
        self, authenticated_client: TestClient, admin_user
    ):
        """Desktop profile dropdown has correct structure: name+email, Admin, Logout."""
        response = authenticated_client.get("/")
        html = response.text

        # Check user name appears in dropdown
        assert admin_user.display_name in html
        # Check logout link exists
        assert "/auth/logout" in html
        # Check admin link exists
        assert 'href="/admin/users"' in html


class TestAdminRoutesAuthorization:
    """Test admin routes require admin role and return 403 for non-admins."""

    def test_admin_users_screen_requires_admin_role(
        self, authenticated_client: TestClient
    ):
        """Admin users can access /admin/users."""
        response = authenticated_client.get("/admin/users")
        assert response.status_code == 200
        # Check that it's the admin page (not error or redirect)
        assert "User Management" in response.text or "Admin" in response.text

    def test_admin_audit_screen_requires_admin_role(
        self, authenticated_client: TestClient
    ):
        """Admin users can access /admin/audit."""
        response = authenticated_client.get("/admin/audit")
        assert response.status_code == 200
        # Check that it's the audit log page
        assert "Audit" in response.text

    def test_non_admin_receives_403_on_admin_users_route(
        self, regular_client: TestClient
    ):
        """Regular users receive 403 when accessing /admin/users."""
        response = regular_client.get("/admin/users")
        assert response.status_code == 403

    def test_non_admin_receives_403_on_admin_audit_route(
        self, regular_client: TestClient
    ):
        """Regular users receive 403 when accessing /admin/audit."""
        response = regular_client.get("/admin/audit")
        assert response.status_code == 403
