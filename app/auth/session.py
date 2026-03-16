from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.settings import settings


def encode_session(user_id: int) -> str:
    """Create signed session cookie value containing user_id."""
    serializer = URLSafeTimedSerializer(settings.SECRET_KEY)
    return serializer.dumps({"user_id": user_id})


def decode_session(cookie: str, max_age: int | None = None) -> dict | None:
    """Decode and validate session cookie.

    Args:
        cookie: The signed session cookie value
        max_age: Maximum age in seconds (defaults to SESSION_MAX_AGE from settings)

    Returns:
        Session data dict with user_id, or None if invalid/expired
    """
    if max_age is None:
        max_age = getattr(settings, "SESSION_MAX_AGE", 86400)

    serializer = URLSafeTimedSerializer(settings.SECRET_KEY)
    try:
        return serializer.loads(cookie, max_age=max_age)
    except SignatureExpired:
        return None
    except BadSignature:
        return None
