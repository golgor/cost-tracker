"""Integration tests for Kubernetes health probe endpoints.

These tests require a running database connection for readiness checks.
Run with: TEST_DATABASE_URL=postgresql://... mise run test:integration
"""

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client for the app."""
    return TestClient(app, raise_server_exceptions=False)


class TestLivenessProbe:
    """Tests for /health/live endpoint (liveness probe)."""

    def test_liveness_is_public(self, client: TestClient):
        """Liveness probe doesn't require authentication."""
        response = client.get("/health/live")
        assert response.status_code == 200

    def test_liveness_returns_ok(self, client: TestClient):
        """Liveness probe returns simple ok status."""
        response = client.get("/health/live")
        data = response.json()
        assert data == {"status": "ok"}


class TestReadinessProbe:
    """Tests for /health/ready endpoint (readiness probe)."""

    def test_readiness_is_public(self, client: TestClient):
        """Readiness probe doesn't require authentication."""
        response = client.get("/health/ready")
        # 200 if DB connected, 503 if not
        assert response.status_code in (200, 503)

    def test_readiness_returns_database_status(self, client: TestClient):
        """Readiness probe returns database connectivity status."""
        response = client.get("/health/ready")
        data = response.json()
        assert "status" in data
        assert "database" in data
        if response.status_code == 200:
            assert data["status"] == "ok"
            assert data["database"] == "connected"
        else:
            assert data["status"] == "unavailable"
            assert data["database"] == "disconnected"
