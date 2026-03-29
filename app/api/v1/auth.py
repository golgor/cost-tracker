"""API key authentication for external API consumers (Glance Dashboard).

Uses FastAPI's HTTPBearer security scheme so Swagger UI shows a proper
"Authorize" button with lock icons on protected endpoints.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.settings import settings

_bearer_scheme = HTTPBearer()


def verify_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
) -> None:
    """Validate Bearer token against GLANCE_API_KEY.

    Raises HTTPException 401/403 if the token is missing or invalid.
    """
    if credentials.credentials != settings.GLANCE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )
