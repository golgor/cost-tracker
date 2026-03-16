from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from starlette.responses import HTMLResponse

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.auth.oidc import get_oauth
from app.auth.session import encode_session
from app.dependencies import get_uow
from app.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login(request: Request):
    """Redirect to Authentik OIDC login."""
    oauth = get_oauth()
    redirect_uri = settings.OIDC_REDIRECT_URI
    return await oauth.authentik.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def callback(request: Request, uow: UnitOfWork = Depends(get_uow)):
    """Handle OIDC callback, provision user if needed, create session."""
    oauth = get_oauth()

    try:
        token = await oauth.authentik.authorize_access_token(request)
    except Exception as e:
        # Handle OIDC errors gracefully
        return HTMLResponse(
            content=f"""
            <html>
            <head><title>Login Error</title></head>
            <body style="font-family: system-ui; padding: 2rem; text-align: center;">
                <h1>Login Failed</h1>
                <p>There was an error during authentication: {str(e)}</p>
                <a href="/auth/login">Try again</a>
            </body>
            </html>
            """,
            status_code=400,
        )

    # Extract user info from ID token
    userinfo = token.get("userinfo", {})
    oidc_sub = userinfo.get("sub")
    email = userinfo.get("email", "")
    display_name = userinfo.get("name") or userinfo.get("preferred_username") or email

    if not oidc_sub:
        return HTMLResponse(
            content="""
            <html>
            <head><title>Login Error</title></head>
            <body style="font-family: system-ui; padding: 2rem; text-align: center;">
                <h1>Login Failed</h1>
                <p>Could not retrieve user information from identity provider.</p>
                <a href="/auth/login">Try again</a>
            </body>
            </html>
            """,
            status_code=400,
        )

    # Auto-provision or update user (FR39)
    user = uow.users.save(
        oidc_sub=oidc_sub,
        email=email,
        display_name=display_name,
    )
    uow.commit()

    # Create session cookie
    session_value = encode_session(user.id)

    # Redirect to dashboard (or setup wizard in future story 1.4)
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        "session",
        session_value,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=settings.SESSION_MAX_AGE,
    )

    return response


@router.get("/logout")
async def logout():
    """Clear session and redirect to login."""
    response = RedirectResponse("/auth/login", status_code=302)
    response.delete_cookie("session")
    response.delete_cookie("csrf_token")
    return response
