from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "postgresql://costtracker:costtracker@localhost:5432/costtracker"
    SECRET_KEY: str = "change-me-in-production"
    OIDC_ISSUER: str = "https://auth.example.com"
    OIDC_CLIENT_ID: str = "cost-tracker"
    OIDC_CLIENT_SECRET: str = "change-me"
    OIDC_REDIRECT_URI: str = "http://localhost:8000/auth/callback"
    SESSION_MAX_AGE: int = 86400  # 24 hours in seconds
    LOG_LEVEL: str = "INFO"
    ENV: str = "dev"  # "dev" | "prod"

    @property
    def is_production(self) -> bool:
        return self.ENV == "prod"


settings = Settings()
