## Admin Interface

### Design Principles

Admin interfaces should be:
- **Clearly separated** from user-facing features — admin access via profile dropdown
- **Cautious with destructive actions** — confirmation dialogs for deactivation
- **Transparent about constraints** — clear error messages when actions are blocked
- **Audit-aware** — every admin action is logged and visible

### Admin Navigation Integration

**Desktop (UX-DR21 extension):**
- Admin menu item appears in the user profile dropdown (upper right corner)
- Dropdown structure:
  - User name + email (non-interactive header)
  - **Admin** (only visible to users with admin role)
  - Logout
- Clicking "Admin" navigates to `/admin/users`
- Profile badge remains consistent with existing design (initials badge + name + chevron)

**Mobile (UX-DR21 extension):**
- Same pattern: admin access via profile dropdown
- Profile dropdown triggered by tapping user badge in top bar (mobile keeps top bar on all screens)
- No changes to bottom nav (remains: Dashboard, Expenses, Recurring, Settlements)

### User Management Screen

**Layout:**
- Card-based table (UX-DR22) with generous whitespace
- Columns: Name, Email, Role (badge), Status (badge), Actions
- Filter tabs at top: All / Active / Deactivated
- Search bar for filtering by name or email

**Role Badges:**
- Admin: Primary accent background (`#C27B5A`), white text
- User: Neutral stone-200 background, dark text

**Status Badges:**
- Active: Green (`#2E7D5B`) background, white text
- Deactivated: Red (`#B8453A`) background, white text

**Action Buttons:**
- Inline on each row (desktop) or expandable menu (mobile)
- Promote/Demote: Neutral stone-colored button
- Deactivate: Danger-styled red button, requires confirmation dialog
- Reactivate: Primary accent button

**Confirmation Dialog (Deactivate):**
- Modal overlay with card (UX-DR22)
- Title: "Deactivate [User Name]?"
- Body: "This user will lose access to the app until reactivated. Historical data is preserved."
- Actions: "Cancel" (neutral) / "Deactivate" (danger-styled, right-aligned)

**Error Handling:**
- Inline error messages appear above the table when actions fail
- Blocked actions (last admin, active groups) show persistent error with explanation
- No toasts — errors stay visible until dismissed (UX-DR24)

### Audit Log Screen

**Layout:**
- Chronological list (newest first) with cards per entry (UX-DR22)
- Each card shows: timestamp (relative + absolute), actor name, action, target user, previous value (if applicable)
- Filter bar (collapsible, UX-DR28 pattern): date range, actor dropdown, action type dropdown
- Pagination: Show last 50 entries, "Load More" button at bottom

**Entry Card Format:**
```
[HH:MM, MMM DD] Golgor promoted Partner to Admin
  Previous role: User
```

**Color Coding:**
- Role changes: Neutral (stone)
- Deactivate: Red accent (`#B8453A`)
- Reactivate: Green accent (`#2E7D5B`)

**Empty State:**
- "No audit entries yet"
- Appears when no actions have been logged

### Admin Section Navigation

**Sub-navigation within admin:**
- Tabs or sidebar: "Users" | "Audit Log"
- Default view: Users

### Responsive Behavior

**Mobile:**
- User table becomes card-based stack (one user per card)
- Action buttons appear as dropdown menu within each card
- Filter controls become bottom sheet (UX-DR4 pattern)

**Desktop:**
- Table layout with inline actions
- Filter controls appear as collapsible bar above table
