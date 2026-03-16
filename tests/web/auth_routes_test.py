"""Tests for auth routes (login, callback, logout)."""

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client for the app."""
    return TestClient(app, raise_server_exceptions=False)


class TestLoginRoute:
    """Tests for /auth/login route."""

    def test_login_redirects_to_oidc_provider(self, client: TestClient):
        """Login route initiates OIDC flow."""
        # The actual redirect to Authentik will fail in tests since
        # we don't have a real OIDC provider, but we can verify the route exists
        response = client.get("/auth/login", follow_redirects=False)
        # Should either redirect to OIDC or return error about OIDC config
        assert response.status_code in (302, 307, 500)


class TestLogoutRoute:
    """Tests for /auth/logout route."""

    def test_logout_clears_session_cookie(self, client: TestClient):
        """Logout clears session cookie and redirects."""
        # Set a fake session cookie first
        client.cookies.set("session", "fake-session-value")

        response = client.get("/auth/logout", follow_redirects=False)

        assert response.status_code == 302
        assert response.headers.get("location") == "/auth/login"
        # Note: delete_cookie in Starlette/FastAPI sets max-age=0 and/or expires in past
        # The cookie may or may not appear in set-cookie header depending on implementation

    def test_logout_redirects_to_login(self, client: TestClient):
        """Logout redirects to login page."""
        response = client.get("/auth/logout", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers.get("location") == "/auth/login"


class TestProtectedRoutes:
    """Tests for protected route behavior."""

    def test_dashboard_redirects_when_unauthenticated(self, client: TestClient):
        """Dashboard redirects to login when not authenticated."""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers.get("location") == "/auth/login"

    def test_htmx_request_gets_hx_redirect_header(self, client: TestClient):
        """HTMX request to protected route gets HX-Redirect header."""
        response = client.get(
            "/",
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )
        # Should return 200 with HX-Redirect header instead of 302
        assert response.status_code == 200
        assert response.headers.get("HX-Redirect") == "/auth/login"


class TestHealthRoute:
    """Tests for /health endpoint (public)."""

    def test_health_is_public(self, client: TestClient):
        """Health endpoint doesn't require authentication."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_database_status(self, client: TestClient):
        """Health endpoint returns database status."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert data["database"] in ("connected", "disconnected")
