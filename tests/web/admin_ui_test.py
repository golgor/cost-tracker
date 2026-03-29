"""Tests for admin UI interface (profile dropdown, user management)."""

import pytest
from starlette.testclient import TestClient

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.auth.session import encode_session
from app.dependencies import get_uow
from app.main import app


@pytest.fixture
def admin_user(uow: UnitOfWork):
    """Create an admin user for testing."""
    with uow:
        user = uow.users.save(
            oidc_sub="admin@test.com",
            email="admin@test.com",
            display_name="Admin User",
        )
        # Promote to admin
        admin = uow.users.promote_to_admin(user.id)

        # Create household group and add user as member
        group = uow.groups.save(
            name="Admin Test Household",
        )
        uow.groups.add_member(
            group_id=group.id,
            user_id=admin.id,
            role="ADMIN",
        )
    return admin


@pytest.fixture
def regular_user(uow: UnitOfWork):
    """Create a regular (non-admin) user for testing."""
    with uow:
        # Get the default group (assumes admin_user fixture created it)
        existing_group = uow.groups.get_default_group()
        if not existing_group:
            # Create group if it doesn't exist
            existing_group = uow.groups.save(
                name="Test Household",
            )

        user = uow.users.save(
            oidc_sub="user@test.com",
            email="user@test.com",
            display_name="Regular User",
        )

        # Add user to the group
        uow.groups.add_member(
            group_id=existing_group.id,
            user_id=user.id,
            role="USER",
        )
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

    def test_admin_user_sees_admin_menu_item_desktop(self, authenticated_client: TestClient):
        """Admin users see 'Admin' menu item in desktop profile dropdown."""
        response = authenticated_client.get("/")
        assert response.status_code == 200

        html = response.text
        # Check for admin link in dropdown
        assert 'href="/admin/users"' in html
        # Check the text "Admin" appears in the navigation area
        assert ">Admin<" in html or "Admin" in html

    def test_regular_user_does_not_see_admin_menu_item_desktop(self, regular_client: TestClient):
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

    def test_admin_users_screen_requires_admin_role(self, authenticated_client: TestClient):
        """Admin users can access /admin/users."""
        response = authenticated_client.get("/admin/users")
        assert response.status_code == 200
        # Check that it's the admin page (not error or redirect)
        assert "User Management" in response.text or "Admin" in response.text

    def test_non_admin_receives_403_on_admin_users_route(self, regular_client: TestClient):
        """Regular users receive 403 when accessing /admin/users."""
        response = regular_client.get("/admin/users")
        assert response.status_code == 403


class TestUserRowViewModel:
    """Unit tests for UserRowViewModel presentation logic."""

    def test_admin_user_row_view_model(self, admin_user):
        """Admin user has correct role label, color, and button visibility."""
        from app.web.view_models import UserRowViewModel

        vm = UserRowViewModel.from_domain(admin_user)

        assert vm.id == admin_user.id
        assert vm.display_name == admin_user.display_name
        assert vm.email == admin_user.email
        assert vm.role_label == "Admin"
        assert "primary-500" in vm.role_badge_color
        assert vm.show_promote is False
        assert vm.show_demote is True  # Default: demote allowed

    def test_regular_user_row_view_model(self, regular_user):
        """Regular user has correct role label, color, and button visibility."""
        from app.web.view_models import UserRowViewModel

        vm = UserRowViewModel.from_domain(regular_user)

        assert vm.id == regular_user.id
        assert vm.role_label == "User"
        assert "stone-200" in vm.role_badge_color
        assert vm.show_promote is True
        assert vm.show_demote is False

    def test_demote_button_disabled_when_last_admin(self, admin_user):
        """Demote button disabled when only 1 active admin exists."""
        from app.web.view_models import UserRowViewModel

        # Test with 1 active admin (the only admin)
        vm = UserRowViewModel.from_domain(admin_user, admin_count=1)

        assert vm.show_demote is False

    def test_demote_button_enabled_when_multiple_admins(self, admin_user):
        """Demote button enabled when multiple active admins exist."""
        from app.web.view_models import UserRowViewModel

        # Test with 2 active admins
        vm = UserRowViewModel.from_domain(admin_user, admin_count=2)

        assert vm.show_demote is True


class TestUserProfileViewModel:
    """Unit tests for UserProfileViewModel presentation logic."""

    def test_admin_profile_view_model(self, admin_user):
        """Admin profile has correct display fields and is_admin flag."""
        from app.web.view_models import UserProfileViewModel

        vm = UserProfileViewModel.from_domain(admin_user)

        assert vm.display_name == admin_user.display_name
        assert vm.email == admin_user.email
        assert vm.is_admin is True
        assert vm.avatar_initial == admin_user.display_name[0].upper()
        # Check member_since format (e.g., "March 18, 2026")
        assert len(vm.member_since) > 0
        assert "," in vm.member_since  # Date format includes comma

    def test_regular_profile_view_model(self, regular_user):
        """Regular profile has is_admin=False."""
        from app.web.view_models import UserProfileViewModel

        vm = UserProfileViewModel.from_domain(regular_user)

        assert vm.is_admin is False
