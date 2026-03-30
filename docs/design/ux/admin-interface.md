# Users Page

## Overview

The users page at `/admin/users` displays both partners in the household. There are no roles,
no promote/demote actions, and no admin hierarchy — both partners are equal.

## Access

- Accessible via the user profile dropdown (both desktop and mobile)
- Profile dropdown structure:
  - User name + email (non-interactive header)
  - **Users** (navigates to `/admin/users`)
  - Logout

## User List

**Layout:**

- Card-based list with two user cards
- Each card shows: Name, Email, Status (Active)

**Responsive Behavior:**

- **Mobile:** Stacked cards (one per row)
- **Desktop:** Table layout or side-by-side cards

## Notes

- User limit is enforced at OIDC login via `MAX_USERS` setting (default 2)
- User records are auto-provisioned from OIDC claims on first login — no manual creation
- No deactivation, role management, or audit log in this view
