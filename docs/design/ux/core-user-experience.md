# Core User Experience

## Defining Experience

Cost-tracker's experience is defined by three complementary loops operating at different frequencies:

**The Daily Loop — Expense Capture** (highest frequency, phone or desktop)
A user pays for something and logs it. Amount, location, save. Under 30 seconds. Smart defaults handle split mode
(even), paid-by (current user), and date (today). The user closes the app and forgets about it until next time. This
loop must be fast and frictionless — but it's not the most critical interaction.

**The Check-in Loop — Review & Maintain** (few times a week, typically desktop)
A user opens the app to check the balance, scan recent expenses, add expenses from online purchases, or act on recurring
cost reminders. This is the connective tissue — it keeps both partners aware of the shared state between settlements.
Partner uses this for batch entry sessions. Golgor uses this when adding non-on-the-go expenses (online orders,
subscriptions) and checking the dashboard. The check-in loop is why the dashboard is the correct home screen — users
land there to get the picture before doing anything else.

**The Monthly Loop — Settlement Review** (lowest frequency, desktop, co-located)
Both partners sit together at a desktop. Golgor initiates the settlement review, and they walk through every unsettled
expense together. They accept or discard each one, watching the settlement total update live. When satisfied, they
confirm — generating a reference ID for the bank transfer. This loop must build absolute confidence: the numbers are
correct, nothing was missed, the process is transparent. Speed matters less than trust here.

The daily loop feeds the check-in loop feeds the monthly loop. If capture is easy, the data is complete. If check-ins
keep both partners aware, the settlement review has no surprises. If the settlement is trustworthy, the system earns
continued use.

## Platform Strategy

**Web application — responsive, server-rendered (FastAPI + Jinja2 + HTMX + Tailwind CSS):**

- **Mobile browser (phone):** Primary context for expense capture. Large touch targets, FAB for "Add Expense," minimal
  scrolling needed for the core action. No native app — browser bookmark is sufficient for the usage frequency. Consider
  a web app manifest for "Add to Home Screen" icon to improve the entry point experience.
- **Desktop browser (laptop):** Primary context for batch entry, dashboard review, and settlement. Wider layouts,
  keyboard-optimized forms, information density appropriate for deliberate review tasks. Settlement flow is desktop-only
  in practice.
- **No broken experiences:** Every screen renders correctly on any device. The app doesn't need to optimize every flow
  for every device, but nothing should look broken or be unusable. Settlement on mobile works (it's just a web page) but
  doesn't need a mobile-optimized layout.
- **No offline support:** The PRD explicitly excludes this. Phone's native note-taking serves as the fallback for
  no-signal moments.
- **No SPA framework:** HTMX provides partial page updates without client-side state management. Every interaction is a
  server round-trip, kept invisible through loading indicators and immediate visual feedback.
- **Static assets vendored:** HTMX (~14KB) and Tailwind CSS bundled. No CDN dependencies, fully self-contained for
  self-hosted deployment.
- **Modern Chrome only:** No legacy browser support, no polyfills. Full use of modern CSS features (container queries,
  `dvh` units, etc.) is available.

## Effortless Interactions

**Must feel effortless (zero friction):**

- Adding an expense: amount → location → save. Three interactions, under 30 seconds. Form resets for immediate next
  entry during batch sessions. Amount and location are both required — two fields, still fast, but ensures every expense
  is scannable at review time.
- Checking the balance: open dashboard, glance at the balance bar. No clicks, no navigation — it's the first thing you
  see.
- Switching between unsettled and settled expense views: single tap/click, instant partial swap via HTMX.
- Copying the settlement reference ID: one click, copied to clipboard, visual confirmation.

**Must feel intuitive (low friction, discoverable):**

- Editing an expense: interaction model (inline edit vs. modal vs. detail page) is an open design question to resolve in
  screen-level design. Must work on both mobile and desktop without accidental edits.
- Adjusting split mode: visible on the form via a descriptive label ("Split: Even") that serves as its own discovery
  mechanism. Tapping/clicking reveals alternatives. The label tells you alternatives exist without demanding you explore
  them.
- Browsing settlement history: chronological list, drill into any past settlement to see included expenses.
- Batch entry on desktop: key open question — persistent form (always visible above feed) vs. re-open form (click button
  each time). Persistent form dramatically improves batch flow. To be resolved in screen-level design.

**Can tolerate friction (correctness over speed):**

- Settlement review: deliberately paced, every expense visible, accept/discard is a conscious choice per item. More
  friction is acceptable here — it builds confidence. Pre-accepted default aligns with trust philosophy (assume expenses
  are correct, review is about finding exceptions).
- Recurring cost management: dedicated view, less frequent interaction. Doesn't need to be instant.

## Critical Success Moments

1. **"The numbers are right"** — The first completed settlement where both partners look at the total, verify it against
   the expenses, and feel confident. This is the moment trust is established. If this moment fails — if there's any
   doubt about correctness — the system loses credibility permanently. *This is the single most important UX moment in
   the product.*

2. **"I can read this instantly"** — The first time Partner opens the expense feed and scans it without confusion.
   Location labels are bold, amounts are clear, paid-by badges tell her who added what, date headers group entries by
   day. She knows what everything is without tapping into details. This is the moment the old system's confusion is
   replaced.

3. **"That was fast"** — The first time Golgor logs an expense in a parking lot in 15 seconds. Amount, "Spar," save.
   Done. Phone goes back in pocket. The moment expense capture becomes a reflex rather than a task. Also: the first time
   Golgor opens the dashboard for a quick check-in and the balance bar instantly tells him the state — green, she owes
   him, roughly 80 EUR. Closes the app. Two seconds.

4. **"It caught my mistake"** — The first time a user enters the wrong amount and catches it during settlement review,
   or the system rejects an invalid split allocation. The system protecting data integrity is a trust-building moment —
   it proves the numbers can be relied on.

5. **"We're done already?"** — The first settlement that takes 10 minutes instead of an hour. Review, confirm, copy
   reference, transfer. The settlement completion moment should feel visually conclusive — not just a button click, but
   a clear "chapter closed" signal. The "receipts in a bowl" era is officially over.

## Experience Principles

**North Star Principle:**

1. **Capture fast, review carefully** — Speed and friction are not uniformly distributed. The daily loop (expense entry)
   is optimized for minimum friction. The monthly loop (settlement review) is optimized for maximum confidence. Never
   sacrifice review clarity for speed. When other principles conflict, this is the tiebreaker: ask which mode the screen
   is serving.

**Design Guidelines:**

1. **Show, don't tell** — Visual indicators over text labels wherever possible. Balance bar over "you owe X." Colored
   initials badge over "paid by Golgor." Date headers over inline date fields. The interface should communicate through
   pattern recognition, not reading.

2. **One obvious action, everything else one tap away** — Every screen has a primary action that's visually dominant and
   immediately reachable. Dashboard → check balance / add expense. Expense feed → scan / add expense. Settlement →
   review and confirm. Secondary features (settlement history, recurring management, audit trail) are reachable from a
   consistent, always-visible navigation structure — not buried behind the primary action.

3. **Feedback proportional to uncertainty** — Self-confirming actions (expense appears in feed) need no extra
   confirmation. Ambiguous or invisible outcomes (errors, settlement confirmation, background saves) get explicit,
   persistent feedback. Don't confirm what the user can already see. This builds the trust that makes settlement review
   credible.

4. **Smart defaults, visible options** — Even split, today's date, logged-in user as payer. These defaults mean most
   expenses need only amount + location. Rarely-used options stay visible through descriptive labels (e.g., "Split:
   Even", "Currency: EUR") that serve as their own discovery mechanism. The user doesn't need to know alternatives exist
   until the label makes them wonder.

5. **One product, two contexts** — Mobile and desktop are layout variations of the same app, not different products.
   Shared visual language, same navigation patterns, same interaction vocabulary scaled to context. Both must render
   correctly everywhere. Features are optimized per task mode but never exclusive to one device.

## Open Design Questions

The following decisions surfaced during core experience definition and need resolution during screen-level design:

| # | Question | Affects | Notes |
| --- | --- | --- | --- |
| 1 | Amount field decimal handling — does "47" mean 47.00? How is "47.5" handled? | Capture loop | Micro-interaction, every expense entry |
| 2 | Mobile form presentation — bottom sheet, modal overlay, or full page? | Capture loop | Bottom sheet keeps feed visible for self-confirmation |
| 3 | Home screen — dashboard confirmed as landing page (supports check-in loop) | All loops | Three-loop model argues for dashboard-as-home |
| 4 | Persistent form vs. re-open for desktop batch entry | Check-in loop | Persistent form dramatically improves Partner's flow |
| 5 | Date picker interaction — calendar widget vs. keyboard-friendly input on desktop | Check-in loop | Keyboard input faster for batch entry |
| 6 | "What's new" indicator — needed, or is newest-first sort sufficient? | Check-in loop | Date headers + sort order may suffice |
| 7 | Settlement completion visual moment — how to signal "chapter closed" | Settlement loop | Should feel conclusive, not just a button click |
| 8 | Pre-accepted vs. pre-unselected default in settlement review | Settlement loop | Pre-accepted aligns with trust philosophy |
| 9 | Undo/re-accept during settlement review — how to reverse a discard | Settlement loop | Must be possible and obvious since review is stateless |
| 10 | "Settle Up" button visibility — always visible or contextual based on unsettled count | Settlement loop | Edge case — what if zero unsettled expenses? |
| 11 | Location field required vs. optional — required improves review quality but adds capture friction | Capture vs. review tension | Trust philosophy says optional; review quality says required |
| 12 | Mobile bottom nav with 4 items + FAB — too crowded? | Navigation | 4 items + elevated FAB may crowd smaller phones. Test at implementation. Consider collapsing to 3 items + "More" or repositioning FAB |
| 13 | Recurring cost definition form — progressive disclosure grouping for 9 fields? | Recurring cost registry | Which fields are primary (always visible) vs. secondary (behind "More options")? See form hierarchy note in Create/Edit flow |
