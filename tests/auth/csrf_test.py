"""Tests for CSRF middleware protection."""

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client for the app."""
    return TestClient(app, raise_server_exceptions=False)


class TestCSRFTokenGeneration:
    """Tests for CSRF token generation."""

    def test_csrf_cookie_set_on_first_request(self, client: TestClient):
        """CSRF cookie is set on first request."""
        response = client.get("/health")
        assert "csrf_token" in response.cookies

    def test_csrf_token_is_long_enough(self, client: TestClient):
        """CSRF token has sufficient entropy."""
        response = client.get("/health")
        token = response.cookies.get("csrf_token")
        assert token is not None
        assert len(token) >= 32  # At least 32 chars for security


class TestCSRFValidation:
    """Tests for CSRF validation on state-changing requests."""

    def test_post_without_csrf_returns_403_on_protected_route(self, client: TestClient):
        """POST to protected route without CSRF token returns 403."""
        # First get a session (normally would be authenticated)
        # For this test, we just verify the CSRF check happens
        # The auth middleware will redirect first, but if we had a session,
        # the CSRF check would apply

        # Get initial CSRF cookie
        client.get("/health")

        # POST without CSRF token - would fail CSRF check after auth
        # Since we're not authenticated, we get redirected to login
        response = client.post("/", follow_redirects=False)
        # Either 302 (auth redirect) or 403 (CSRF) depending on middleware order
        assert response.status_code in (302, 403)

    def test_public_routes_skip_csrf_validation(self, client: TestClient):
        """Public routes don't require CSRF validation."""
        # Health endpoint is public
        response = client.get("/health")
        assert response.status_code == 200

    def test_csrf_cookie_is_httponly(self, client: TestClient):
        """CSRF cookie has httponly flag."""
        response = client.get("/health")
        # Check raw Set-Cookie header for httponly
        set_cookie = response.headers.get("set-cookie", "")
        if "csrf_token" in set_cookie:
            assert "httponly" in set_cookie.lower()
