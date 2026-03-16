# UX Pattern Analysis & Inspiration

## Inspiring Products Analysis

**Swish (Swedish payment app)**
The primary UX inspiration for expense capture. Swish's QR payment flow embodies the ideal: scan → everything pre-filled except amount → enter amount → done. Three qualities make it feel instant:
1. **No navigation** — the action starts immediately, no menu traversal
2. **Pre-filled context** — recipient, reference, everything except the variable (amount) is already set
3. **Minimal fields** — one thing to type, everything else handled

For cost-tracker, the translation differs by device context:
- **Mobile:** Open app → tap FAB → amount field auto-focused with numeric keyboard (`inputmode='decimal'`) → type amount → tap location field → type location → tap save. No tab key on mobile — the sequence is tap-based.
- **Desktop:** Open app → click Add Expense → amount field auto-focused → type amount → tab to location → type location → enter to save. Keyboard-driven, optimized for batch entry flow.

The Swish pattern proves that "pre-fill + one variable" creates the feeling of instant capture. Cost-tracker has two variables (amount + location), but smart defaults handle everything else.

**Spliit (expense splitting web app)**
Referenced for the balance visualization pattern. Spliit's horizontal bar with red/green colors and names + amounts on each side communicates balance state faster than any text could. The pattern works because:
1. **Color = direction** — red means you owe, green means you're owed
2. **Length = magnitude** — the bar proportionally shows how much
3. **Labels = clarity** — names and amounts remove ambiguity

For cost-tracker, this translates directly to the dashboard balance bar. With only 2 users, it's a single bar — the simplest possible version of this pattern.

**Stripe Checkout (payment flow)**
Referenced for the settlement flow pattern. Stripe Checkout's multi-step flow maps directly to cost-tracker's settlement: review items → confirm total → success screen. Key qualities:
1. **Progress indicator** — clear sense of where you are in the flow (step 1 of 3, step 2 of 3)
2. **Running total** — the amount updates as items are reviewed
3. **Conclusive success state** — a clear "done" screen with checkmark and summary, not just a flash message

For cost-tracker's settlement: review expenses (with live-updating total as items are accepted/discarded) → confirm settlement (with transfer direction and amount) → success screen (reference ID prominently displayed, copy button, clear "chapter closed" visual signal).

**WhatsApp (messaging)**
Referenced for interaction directness. WhatsApp's core lesson: open → you're already in context → type → send. No "navigate to messaging" step. The conversation is the home screen.

For cost-tracker: the dashboard is the home screen (you're immediately in context), and the Add Expense action is always one tap away from anywhere. The app never asks "what do you want to do?" — it shows you the state and offers the obvious next action.

**The old system (home-automation-hub)**
Referenced as the anti-pattern baseline. The old system's failures define cost-tracker's requirements by inversion:
- Adding an expense required navigating to the expense list first → cost-tracker: Add Expense available from anywhere
- Labels were unclear → cost-tracker: descriptive labels, no abbreviations or icons-only
- The flow was confusing → cost-tracker: one obvious action per screen, consistent navigation

No positive patterns carried forward — cost-tracker is a clean break in UX design.

## Transferable UX Patterns (By Screen/Flow)

**Dashboard Patterns:**
- **Balance bar (Spliit)** — red/green horizontal bar with names and amounts. The visual anchor. Instant state communication.
- **Home-as-context (WhatsApp)** — the dashboard is the landing page. Users arrive in context, not at a menu. Supports the check-in loop.
- **Widget-based layout** — each dashboard section (balance, recurring overview, recent expenses) is a self-contained partial, independently refreshable via HTMX.

**Expense Capture Patterns:**
- **Pre-fill + minimal input (Swish)** — smart defaults handle split, payer, date, currency. Only amount and location need user input.
- **Mobile: tap-based sequence** — FAB → auto-focused amount field with `inputmode='decimal'` → tap location → tap save. No keyboard tab flow on mobile.
- **Desktop: keyboard-driven sequence** — click Add Expense → auto-focused amount → tab → location → enter to save. Optimized for batch entry with form reset after save.
- **FAB always reachable** — floating action button on mobile, toolbar button on desktop. Never navigate to a list first.

**Expense Feed Patterns:**
- **Scan-and-recognize (WhatsApp)** — location/merchant as the bold primary text (like a contact name), amount as supporting text, paid-by badge for attribution, date headers for grouping. Scan, recognize, move on.
- **Minimal chrome, maximum content** — all visual weight on expense data, not on UI decoration. Card-based layout with generous whitespace — modern and clean, not raw HTML forms.

**Settlement Flow Patterns:**
- **Multi-step guided flow (Stripe Checkout)** — progress indicator, review → confirm → success. Each step has a clear purpose and visible progress.
- **Live-updating total** — the settlement amount updates as expenses are accepted/discarded during review, building confidence in the final number.
- **Conclusive success state** — a dedicated completion screen with reference ID, transfer instructions, and a clear visual "done" signal. Not a toast, not a redirect — a moment.

## Anti-Patterns to Avoid

- **Navigate-to-act (old system)** — requiring users to find the right screen before they can perform the primary action. Every "where do I click?" moment is a failure.
- **Form-heavy capture** — apps that show 8+ fields for expense entry (category dropdowns, receipt upload, tax toggles). Every optional field visible during capture adds cognitive load. Show only amount + location; everything else is secondary. (Note: the recurring cost definition form has 9 fields but is a "tolerate friction" interaction — uses progressive disclosure to manage complexity. See Open Design Question #13.)
- **Raw HTML form aesthetic** — server-rendered doesn't mean ugly. Forms should be card-based with whitespace, rounded inputs, clear visual hierarchy. Tailwind makes this straightforward but it must be an intentional design direction, not an afterthought.
- **Perspective-relative balance done wrong** — apps that show "you owe X" without clear visual grounding. With OIDC authentication, the app knows who "you" is, so the balance bar can highlight the authenticated user's side. Balance statements still use neutral transfer language ("Transfer X from A to B") for clarity, but the user's side is visually emphasized.
- **Silent actions** — apps where you click save and nothing visibly changes. Feedback should be proportional to uncertainty — self-confirming actions (expense appears in feed) need no extra banner, but ambiguous outcomes need explicit feedback.
- **Notification-driven engagement** — expense tracking apps that push reminders, nudges, and "you haven't logged today" messages. Cost-tracker's philosophy is trust over enforcement. The app is there when you need it; it doesn't chase you.
- **Overcomplicated settlement** — apps that require multiple confirmation screens, email verification, or mandatory comments before settling. The 3-step flow (review → approve → confirm) is the right amount of ceremony.

## Design Inspiration Strategy

**What to Adopt:**
- Swish's "pre-fill + minimal input" pattern → expense form with smart defaults, only amount and location as perceived inputs
- Spliit's color-coded balance bar → dashboard balance visualization with names, amounts, and directional color
- Stripe Checkout's multi-step flow → settlement with progress indicator, live total, and conclusive success screen
- WhatsApp's "home = context" directness → dashboard as home screen with Add Expense always reachable
- Card-based, whitespace-forward visual tone → modern Tailwind utility styling, not raw form elements

**What to Adapt:**
- Swish's single-field flow → two fields (amount + location), adapted with auto-focus progression. Mobile uses tap-based sequence; desktop uses keyboard tab flow
- Spliit's balance bar → simplified for 2 users (single bar). In MVP2 with multiple participants, expand to per-person bars
- Stripe Checkout's item review → expense review with accept/discard per item and live-updating total, adapted for co-located two-person review
- WhatsApp's conversation-list scannability → expense feed with location as bold primary text, amount as supporting text, paid-by badge, and date headers

**What to Avoid:**
- Any pattern that requires navigation before action
- Any pattern that surfaces optional complexity during the primary flow
- Any pattern that assumes per-user identity without leveraging the OIDC session (the session is the source of truth for who is logged in)
- Any notification or engagement pattern — the app is passive, not pushy
- Any visual design that defaults to raw HTML — intentional card-based styling from day one
