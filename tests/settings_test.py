"""Tests for application settings validation."""

import pytest
from pydantic import ValidationError

from app.settings import Settings


def _prod_base() -> dict:
    """Minimal valid production settings.

    Always includes _env_file=None so pydantic-settings does not read the
    local .env file, keeping tests hermetic regardless of dev overrides.
    """
    return {
        "_env_file": None,
        "DATABASE_URL": "postgresql://user:pass@localhost/db",
        "SECRET_KEY": "a-very-secure-secret-key-for-production",
        "OIDC_ISSUER": "https://issuer.example.com",
        "OIDC_CLIENT_ID": "client-id",
        "OIDC_CLIENT_SECRET": "a-secure-oidc-secret",
        "OIDC_REDIRECT_URI": "https://app.example.com/auth/callback",
        "INTERNAL_WEBHOOK_SECRET": "a-secure-webhook-secret",
        "GLANCE_API_KEY": "a-secure-glance-key",
        "ENV": "prod",
    }


class TestProductionSettingsValidation:
    def test_dev_bypass_auth_rejected_in_production(self):
        """DEV_BYPASS_AUTH=True must cause startup failure when ENV=prod."""
        with pytest.raises(
            ValidationError, match="DEV_BYPASS_AUTH must not be enabled in production"
        ):
            Settings(**{**_prod_base(), "DEV_BYPASS_AUTH": True})

    def test_dev_bypass_auth_allowed_in_dev(self):
        """DEV_BYPASS_AUTH=True is valid when ENV=dev."""
        settings = Settings(
            _env_file=None,
            DATABASE_URL="postgresql://user:pass@localhost/db",
            SECRET_KEY="any-key",
            OIDC_ISSUER="https://issuer.example.com",
            OIDC_CLIENT_ID="client-id",
            OIDC_CLIENT_SECRET="any-secret",
            OIDC_REDIRECT_URI="https://app.example.com/auth/callback",
            ENV="dev",
            DEV_BYPASS_AUTH=True,
        )
        assert settings.DEV_BYPASS_AUTH is True

    def test_dev_bypass_auth_defaults_to_false(self):
        """DEV_BYPASS_AUTH defaults to False so it is never accidentally enabled."""
        settings = Settings(**_prod_base())
        assert settings.DEV_BYPASS_AUTH is False
