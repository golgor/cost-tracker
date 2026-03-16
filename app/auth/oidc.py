from authlib.integrations.starlette_client import OAuth

from app.settings import settings

oauth = OAuth()

oauth.register(
    name="authentik",
    client_id=settings.OIDC_CLIENT_ID,
    client_secret=settings.OIDC_CLIENT_SECRET,
    server_metadata_url=f"{settings.OIDC_ISSUER}/.well-known/openid-configuration",
    client_kwargs={"scope": "openid profile email"},
)


def get_oauth() -> OAuth:
    """Get the configured OAuth client."""
    return oauth
