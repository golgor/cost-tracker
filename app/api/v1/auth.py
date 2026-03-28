"""API key authentication for external API consumers (Glance Dashboard)."""

from typing import Annotated

from fastapi import Header, HTTPException, status

from app.settings import settings


def verify_api_key(authorization: Annotated[str | None, Header()] = None) -> None:
    """Validate Authorization: Bearer <key> header against GLANCE_API_KEY.

    Raises HTTPException 401 if the key is missing or invalid.
    """
    expected = f"Bearer {settings.GLANCE_API_KEY}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
