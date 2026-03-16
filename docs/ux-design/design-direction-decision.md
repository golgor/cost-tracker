# Design Direction Decision

## Design Directions Explored

Seven design areas were explored through an interactive HTML showcase (`ux-design-directions.html`), with multiple variations per area:

1. **Color Palette** — Full warm earth-tone palette rendered with semantic color mapping, paid-by badge colors, and balance bar colors
2. **Dashboard Layout** — Two directions: (A) Balance-first with clean expense feed, (B) Dashboard with stat widgets and summary cards
3. **Card Density** — Two options: Compact (tight spacing) vs. Airy (generous breathing room)
4. **Mobile Capture** — Bottom sheet with amount as hero field, smart default chips
5. **Desktop Capture** — Two approaches: Sidebar form (always visible) vs. Inline form (within the feed)
6. **Settlement Flow** — 3-step guided flow: review → confirmation gate → success screen
7. **Navigation** — Mobile bottom nav with FAB, desktop top nav with logo placeholder

## Chosen Direction

A merged approach combining the best elements from multiple directions, refined through three rounds of iteration:

**Dashboard — Merged A+B:**

- Balance bar as the hero element — no label, self-explanatory (partner names + amounts + color convey everything)
- Two stat widgets below the balance bar: tappable "Unsettled" count (primary color, navigates to settlement flow) + informational "This Month" total (sum of all shared expenses in the current calendar month, both partners combined, regardless of settlement status — spending awareness, not balance tracking)
- Recent expense feed scrolling below — no "Recent" header or "All Expenses" link needed (scrolling the feed IS the "all expenses" view)
- No dedicated "Settle Up" button on the dashboard — settlement is a ~1%/month action; the tappable unsettled count widget serves as the contextual entry point
- When unsettled count is 0, the widget becomes inert (muted styling, no arrow, not clickable)

**Card Density — Airy:**

- Generous spacing throughout, consistent with the visual foundation's "airy but purposeful" principle

**Mobile Capture — Bottom Sheet:**

- Amount as hero field, "Where / What" combined label, smart default chips for common expenses

**Desktop Capture — Sidebar:**

- Always-visible sidebar form for batch entry, "Save & Next" flow for rapid sequential input

**Settlement Flow — 3-Step Guided:**

- Step 1: Review with pre-accepted checkboxes (uncheck to exclude)
- Step 2: Confirmation gate with clear amount and direction
- Step 3: Amber success screen with reference ID

**Navigation:**

- Mobile: bottom nav (4 items) + FAB for quick expense entry
- Desktop: top nav with logo placeholder (no brand text), nav items left-aligned, "+ Add Expense" button right-aligned, authenticated user's name/initials badge far-right (from OIDC session — confirms who is logged in, with a dropdown for logout)

## Design Rationale

- **Balance-first dashboard** puts the single most important data point front and center — aligns with the "glanceable state" principle from the core experience
- **Stat widgets** replace unnecessary navigation links with actionable information — the unsettled count creates a natural, contextual path to settlement without a dedicated button cluttering the dashboard for a rare action
- **Airy density** reinforces the "shared notebook" feel — not a dense financial tool, but a light household utility
- **Sidebar for desktop** supports Partner's batch-entry workflow — the form is always present, reducing friction for sequential input
- **Bottom sheet for mobile** supports Golgor's on-the-go capture — minimal taps, amount first, done in 30 seconds
- **3-step settlement** with pre-accepted checkboxes and a confirmation gate prevents accidental settlements while keeping the happy path fast (most months, all expenses are correct → just confirm)
- **No brand text in desktop nav** keeps the header clean and functional — the logo placeholder is sufficient for a self-hosted app used by two people. The authenticated user's name/initials badge on the far-right provides identity confirmation and a logout action

## Implementation Approach

**HTML showcase as living reference:**

- `ux-design-directions.html` serves as the visual reference throughout implementation
- Uses CSS custom properties matching the exact Tailwind design tokens
- All mockups are interactive with hover states and transitions

**Phased implementation mapping:**

- **MVP1a:** Dashboard (balance bar + widgets + feed), mobile bottom sheet capture, navigation shell
- **MVP1b:** Settlement flow (3 steps), unsettled count widget becomes tappable
- **MVP1c:** Split mode selection in capture forms
- **MVP1d:** Desktop sidebar form for batch entry, recurring cost registry + engine flows

**Design token bridge:**

- The HTML showcase's CSS custom properties map directly to Tailwind config values
- Implementation should reference the Tailwind config from the Visual Foundation section, not the HTML file's CSS variables
- Component patterns in the showcase inform Jinja2 partial structure
