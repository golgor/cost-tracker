from pydantic import ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRETS = {
    "change-me-in-production",
    "change-me",
    "test-secret-key-not-for-production",
    "change-me-webhook-secret",
    "change-me-glance-api-key",
}


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All fields are required - the app will fail to start if not configured.
    Use a .env file for local development.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str
    SECRET_KEY: str
    OIDC_ISSUER: str
    OIDC_CLIENT_ID: str
    OIDC_CLIENT_SECRET: str
    OIDC_REDIRECT_URI: str
    SESSION_MAX_AGE: int = 86400  # 24 hours in seconds
    LOG_LEVEL: str = "INFO"
    ENV: str = "dev"  # "dev" | "prod"
    INTERNAL_WEBHOOK_SECRET: str = "change-me-webhook-secret"
    GLANCE_API_KEY: str = "change-me-glance-api-key"
    SYSTEM_ACTOR_ID: int = 0  # ID used for automated system-initiated actions

    @property
    def is_production(self) -> bool:
        return self.ENV == "prod"

    @model_validator(mode="after")
    def validate_production_settings(self) -> Settings:
        """Validate settings are secure for production."""
        if self.is_production:
            if self.SECRET_KEY in _INSECURE_SECRETS:
                raise ValueError("SECRET_KEY must be set to a secure value in production")
            if self.OIDC_CLIENT_SECRET in _INSECURE_SECRETS:
                raise ValueError("OIDC_CLIENT_SECRET must be set in production")
            if self.INTERNAL_WEBHOOK_SECRET in _INSECURE_SECRETS:
                raise ValueError(
                    "INTERNAL_WEBHOOK_SECRET must be set to a secure value in production"
                )
            if self.GLANCE_API_KEY in _INSECURE_SECRETS:
                raise ValueError(
                    "GLANCE_API_KEY must be set to a secure value in production"
                )
        return self


def _load_settings() -> Settings:
    """Load settings with user-friendly error on missing configuration."""
    try:
        return Settings()  # type: ignore[call-arg]  # ty: ignore[missing-argument]  # pydantic-settings reads from env vars
    except ValidationError as e:
        missing = [err["loc"][0] for err in e.errors() if err["type"] == "missing"]
        if missing:
            import sys

            print("\n❌ Missing required environment variables:", file=sys.stderr)
            for field in missing:
                print(f"   • {field}", file=sys.stderr)
            print("\nCreate a .env file or set these environment variables.", file=sys.stderr)
            print("See .env.example for reference.\n", file=sys.stderr)
            sys.exit(1)
        raise


settings = _load_settings()
