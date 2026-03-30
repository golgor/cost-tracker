# Executive Summary

## Project Vision

Cost-tracker is a self-hosted household expense-sharing app for two partners in an ongoing relationship. Unlike
event-based splitters (Splitwise) or budgeting tools (YNAB), it's designed for the continuous rhythm of shared living
expenses: log as you go, settle monthly, transfer via bank, repeat.

The UX philosophy mirrors the product philosophy: trust over enforcement, speed over completeness, clarity over
features. The app should feel like a shared notebook — quick to jot in, easy to review, impossible to get lost in.

**Two modes, two mindsets:**

- **Capture** succeeds when you forget about it — 30 seconds, in and out
- **Review** succeeds when the picture sticks — glanceable dashboard with visual balance indicator that imprints the
  state at a glance

## Target Users

### Golgor (Primary — On-the-go logger)

- Logs expenses immediately after purchase, typically on phone
- Initiates and drives the monthly settlement process (desktop, co-located with Partner)
- Also the system admin/deployer
- Wants: fast entry, clear balance visibility, confident settlement flow

### Partner (Primary — Batch reviewer)

- Accumulates receipts during the week, enters them in a batch session on laptop
- Reviews settlements co-located with Golgor — they sit together and go through it
- Key frustration with previous system: unclear labels and a broken flow — adding an expense required navigating to the
  expense list first, then finding a button within it
- Wants: obvious UI with clear primary actions, easy batch entry with keyboard-optimized tab order, quick visual
  scanning of expense history

Both are co-admins with equal permissions. Neither is particularly technical in a UX sense — the interface must be
immediately obvious.

## Key Design Challenges

1. **Navigation clarity and direct action access** — Partner's main pain points with the old system were unclear labels
   and a broken flow: adding an expense required navigating to the expense list first, then finding a button within it.
   The fix is twofold: clear labeling throughout, and primary actions (especially "Add Expense") accessible from
   anywhere without navigating to their parent view first. On mobile, a large floating action button (FAB) for
   one-handed thumb reach. On desktop, an integrated toolbar button that doesn't obscure content during batch entry.
2. **Two task modes, one interface** — Capture (phone, parking lot, 15 seconds) vs. Review (desktop, deliberate,
   dashboard + settlement). Same templates, CSS-driven layout differences, but the *information priority* and
   *interaction pattern* shifts between modes. Design for the task, not the device.
3. **Settlement as a co-located activity** — Both partners sit together to review and confirm. Golgor drives, Partner
   follows along on the same screen. The UX must be readable at arm's length for the non-driver: clear text, obvious
   groupings, and a live-updating settlement total as expenses are accepted/discarded.
4. **Expense list scannability** — The merchant/location field (e.g., "Spar", "Shell") carries implicit category
   meaning. The expense feed must make this field visually prominent so users can scan and understand at a glance.
   Additional scannability requirements: paid-by indicator (initials on a colored badge), and date grouping/headers for
   orientation — visual separation by day supports Partner's batch-entry verification ("what have I already entered?").
5. **Server-rendered feedback loop** — Every user action requires a server round-trip (HTMX architecture). The UX must
   make this invisible through loading indicators on interactive elements, immediate visual confirmation on success
   (expense appears in feed), and persistent inline errors on failure. No silent failures, no toasts that disappear —
   Partner must always know whether her action worked.
6. **Batch entry ergonomics** — Partner's primary interaction is rapid sequential entry on desktop. Tab order, keyboard
   flow, and form reset behavior after save are critical. The form must support "save and immediately start next"
   without re-navigating or losing context.

## Design Opportunities

1. **Location typeahead with progressive enhancement** — Ship as a plain text field initially. Later, upgrade to a
   client-side filtered dropdown from a pre-loaded list of previously used locations (small vendored JS component).
   Keeps the core stack pure while delivering the smart shortcut later. Top 5-10 locations likely cover 80% of entries.
2. **"Add Expense" as the hero action, always reachable** — A persistent, unmissable entry point on every screen
   (especially mobile) that never requires navigating to the expense list first. This directly addresses the old
   system's core failure. Balance summary is important but secondary — it's a deliberate check on the dashboard, not the
   first thing competing for attention.
3. **Settlement as a guided ceremony** — The 3-step flow (review → approve → confirm with reference ID) can feel
   satisfying and conclusive — like closing a chapter each month. Desktop-only allows wider layouts, step indicators,
   and more information density. Live-updating total as expenses are accepted/discarded builds confidence. The reference
   ID copy-to-clipboard moment is the payoff. Optimized for two people viewing one screen.
4. **Graphical balance indicator** — A single horizontal bar (red/green, inspired by Spliit's balance visualization)
   showing the balance direction and magnitude between the two partners. Includes names and amounts on each side — the
   authenticated user's side is visually emphasized (e.g., subtle highlight or "You" label) since OIDC session
   identifies who is viewing. Communicates state faster than numbers and serves as the visual anchor of the dashboard.

## Discovery Notes

- **PRD Gap: Location/Merchant field** — The PRD defines "description" and "notes" on expenses, but user workflows treat
  the primary text field as a merchant/location identifier (e.g., "Spar", "Shell") rather than a free-text description.
  The field label should be flexible enough for physical locations ("Spar"), services ("Netflix"), and general
  descriptions ("birthday supplies"). Consider "Where / What" as the label or a prominent placeholder. Recommendation:
  reframe "description" in the PRD accordingly, with "notes" remaining as optional additional context. Affects FR1 and
  the expense form design. To be reconciled with PRD separately.
- **HTMX constraint: Location typeahead** — Server round-trip typeahead is feasible but latency-sensitive.
  Recommendation is client-side filtering from a pre-loaded location list to avoid tight server loops.
- **Settlement workflow model** — Settlement is a co-located activity: both partners sit together, Golgor drives the
  review on one screen, Partner follows along and discusses. No async handoff, no notifications needed. The stateless
  review model in the PRD (FR21) aligns with this — no state to track between sessions. The UX should prioritize
  readability for the non-driver (clear text, obvious groupings, sufficient size).
- **Expense form hierarchy** — Amount + location/merchant are the dominant fields (large, prominent). Who-paid, date,
  split mode are present but visually quieter with smart defaults. Notes behind a secondary interaction. The form is not
  progressive disclosure — all primary fields visible, but visual weight communicates priority.
