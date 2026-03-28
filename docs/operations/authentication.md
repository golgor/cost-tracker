# Authentication

Cost Tracker uses OpenID Connect (OIDC) for authentication. Any OIDC-compliant provider works;
this guide uses [Authentik](https://goauthentik.io/) as the reference.

## How It Works

1. User navigates to the app and is redirected to the OIDC provider
2. User authenticates with the provider (username/password, SSO, etc.)
3. Provider redirects back to the app with an authorization code
4. App exchanges the code for user info (subject, email, display name)
5. App creates or updates the local user record
6. A signed session cookie is set — no server-side session store

```text
Browser → /auth/login → Authentik → /auth/callback → signed cookie → Dashboard
```

## Setting Up Authentik

### 1. Create an Application

In Authentik:

1. Go to **Applications** > **Create**
2. Set the name (e.g., "Cost Tracker")
3. Select or create a provider (see next step)

### 2. Create an OAuth2/OIDC Provider

1. Go to **Providers** > **Create** > **OAuth2/OpenID Connect**
2. Configure:

   | Setting | Value |
   | --- | --- |
   | Name | Cost Tracker Provider |
   | Authorization flow | default-provider-authorization-implicit-consent |
   | Client type | Confidential |
   | Redirect URIs | `https://costs.example.com/auth/callback` |
   | Scopes | `openid`, `profile`, `email` |

3. Note the **Client ID** and **Client Secret** — you'll need these for configuration

### 3. Get the Issuer URL

The issuer URL follows this pattern for Authentik:

```text
https://auth.example.com/application/o/<application-slug>/
```

The app uses this URL to discover the OIDC endpoints via
`.well-known/openid-configuration`.

### 4. Configure Cost Tracker

Set these environment variables:

```text
OIDC_ISSUER=https://auth.example.com/application/o/cost-tracker/
OIDC_CLIENT_ID=<client-id-from-authentik>
OIDC_CLIENT_SECRET=<client-secret-from-authentik>
OIDC_REDIRECT_URI=https://costs.example.com/auth/callback
```

The redirect URI must exactly match what you configured in Authentik.

## Using Other OIDC Providers

Any provider that supports OpenID Connect works. You need:

- An issuer URL that serves `.well-known/openid-configuration`
- A confidential client with `openid`, `profile`, and `email` scopes
- A redirect URI pointing to `/auth/callback`

Examples:

| Provider | Issuer URL pattern |
| --- | --- |
| Authentik | `https://auth.example.com/application/o/<app>/` |
| Keycloak | `https://auth.example.com/realms/<realm>` |
| Auth0 | `https://<tenant>.auth0.com/` |
| Google | `https://accounts.google.com` |

## Session Management

Sessions use **signed cookies** (via itsdangerous):

- Cookie name: `cost_tracker_session`
- Content: signed `user_id` (no sensitive data stored)
- Flags: `HttpOnly`, `SameSite=Lax`, `Secure` (production only)
- Default lifetime: 24 hours (configurable via `SESSION_MAX_AGE`)
- No server-side session store — the cookie is self-contained

Sessions are invalidated on:

- Logout (`/auth/logout` clears the cookie)
- Expiration (time-based, checked on every request)
- Secret key rotation (changing `SECRET_KEY` invalidates all sessions)

## CSRF Protection

All state-changing requests (POST, PUT, DELETE, PATCH) are protected by CSRF tokens:

- A `csrf_token` cookie is set on first visit
- HTMX requests send the token via `X-CSRF-Token` header
- Form submissions include it as a `_csrf_token` hidden field

This is handled automatically by the middleware — no manual configuration needed.

## First User Bootstrap

The first user to log in is automatically promoted to **app admin**. This user can then:

- Manage other users (promote, demote, deactivate)
- View audit logs
- The setup wizard creates the initial household group

Subsequent users who log in via OIDC are automatically provisioned as regular users and
added to the default group.

## Troubleshooting

### Login redirects fail or loop

- Verify `OIDC_REDIRECT_URI` matches exactly in both the app config and OIDC provider
- For local development, use `http://localhost:8000/auth/callback`
- For production, use HTTPS: `https://costs.example.com/auth/callback`

### "State mismatch" error after login

- Usually caused by stale cookies — clear browser cookies and try again
- The app handles this automatically by clearing cookies and restarting the flow

### User is deactivated

- Deactivated users see a 403 error page on login
- An admin must reactivate the user via the admin panel

### CSRF validation fails

- Ensure cookies are enabled in the browser
- For HTMX: verify the `X-CSRF-Token` header is being sent
- For forms: verify the `_csrf_token` hidden field is present
