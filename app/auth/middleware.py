import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from app.auth.session import decode_session
from app.settings import settings

PUBLIC_PATHS = {"/auth/login", "/auth/callback", "/health", "/static"}
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"
CSRF_FORM_FIELD = "_csrf_token"


def is_htmx_request(request: Request) -> bool:
    """Check if request is an HTMX request."""
    return request.headers.get("HX-Request") == "true"


def is_public_path(path: str) -> bool:
    """Check if path is public (no auth required)."""
    return any(path.startswith(p) for p in PUBLIC_PATHS)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce authentication on protected routes."""

    async def dispatch(self, request: Request, call_next):
        # Skip auth for public paths
        if is_public_path(request.url.path):
            return await call_next(request)

        # Check session cookie
        session_cookie = request.cookies.get("cost_tracker_session")
        if not session_cookie:
            return self._redirect_to_login(request)

        session_data = decode_session(session_cookie, settings.SESSION_MAX_AGE)
        if not session_data:
            return self._redirect_to_login(request)

        # Store user_id in request state for dependencies
        request.state.user_id = session_data["user_id"]

        return await call_next(request)

    def _redirect_to_login(self, request: Request) -> Response:
        """Redirect to login, handling HTMX requests specially."""
        if is_htmx_request(request):
            return Response(
                status_code=200,
                headers={"HX-Redirect": "/auth/login"},
            )
        return RedirectResponse("/auth/login", status_code=302)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Middleware for CSRF protection on state-changing requests."""

    async def dispatch(self, request: Request, call_next):
        # Get or generate CSRF token
        csrf_token = request.cookies.get(CSRF_COOKIE)
        if not csrf_token:
            csrf_token = secrets.token_urlsafe(32)

        # Store token in request state for templates
        request.state.csrf_token = csrf_token

        # Validate on state-changing methods (except public paths)
        is_state_changing = request.method in ("POST", "PUT", "DELETE", "PATCH")
        needs_csrf = is_state_changing and not is_public_path(request.url.path)
        if needs_csrf and not await self._validate_csrf(request, csrf_token):
            return Response(
                content="CSRF validation failed",
                status_code=403,
            )

        response = await call_next(request)

        # Set CSRF cookie if not present
        if not request.cookies.get(CSRF_COOKIE):
            response.set_cookie(
                CSRF_COOKIE,
                csrf_token,
                httponly=True,
                samesite="lax",
                secure=settings.is_production,
            )

        return response

    async def _validate_csrf(self, request: Request, expected_token: str) -> bool:
        """Validate CSRF token from header or form field."""
        # Check header first (for HTMX requests)
        header_token = request.headers.get(CSRF_HEADER)
        if header_token == expected_token:
            return True

        # Check form field for regular form submissions
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("application/x-www-form-urlencoded"):
            try:
                form = await request.form()
                form_token = form.get(CSRF_FORM_FIELD)
                if form_token == expected_token:
                    return True
            except Exception:
                pass

        return False
