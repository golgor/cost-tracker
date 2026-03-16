# Design System Foundation

## Design System Choice

**Tailwind CSS + Custom Jinja2 Component Partials** — no component library, no CSS framework on top of Tailwind. The
design system is a small set of reusable Jinja2 template partials styled with Tailwind utility classes, plus a design
token configuration in `tailwind.config.js`.

## Rationale for Selection

- **Stack alignment** — Tailwind is already the chosen CSS framework (PRD). Adding a component library on top adds a
  dependency without meaningful benefit for a ~5-screen app.
- **Server-rendered compatibility** — Jinja2 template partials work directly with Tailwind classes. No JavaScript
  framework dependency, no build-time component compilation. The "component" is a `.html` partial file with Tailwind
  classes.
- **Solo developer simplicity** — fewer abstractions to maintain. When you want to change a button style, you edit the
  Tailwind classes on the partial — no theme configuration, no override hierarchy, no "how do I customize this component
  library's default?"
- **Full visual control** — the card-based, whitespace-forward visual tone identified in the inspiration analysis is
  achievable with Tailwind utilities alone. No fighting against a library's opinionated defaults.
- **Zero runtime cost** — Tailwind CLI generates a single CSS file at build time from template usage. No additional CSS
  payload beyond what's actually used.

## Implementation Approach

**Design Tokens (tailwind.config.js):**

- Color palette: warm primary accent (teal/indigo range — household tool, not corporate dashboard), success (green —
  owed), danger (red — owes), neutral grays, background/surface colors. Green/red reserved exclusively for balance
  direction; primary accent used for navigation, buttons, and interactive elements.
- Spacing scale: consistent padding/margin tokens for cards, form fields, feed items
- Typography: font sizes for amount display (large), location labels (medium-bold), metadata (small-muted)
- Border radius: consistent rounding for cards, inputs, badges, buttons
- Shadows: subtle elevation for cards and bottom sheets

**Development Workflow:**

- **Local development:** `tailwind --watch` for rapid iteration — CSS regenerates on every template change
- **Production build:** `tailwind build` runs during Docker image build, generating optimized CSS from template usage.
  No Node.js runtime dependency in the container.

**HTMX Transition Baseline (MVP1a):**

- `htmx-swapping` and `htmx-settling` CSS classes defined from day one
- Simple 150ms opacity fade on content swap — prevents the "flash of empty content" that makes HTMX swaps look broken
- Three lines of CSS, massive perceived quality improvement. This is baseline, not polish.

**Reusable Jinja2 Partials (the "component library"):**

| Partial | Purpose | Used In |
|---|---|---|
| `_expense_card.html` | Expense item in feed — location bold, amount, paid-by badge, date, status | Expense feed, settlement review |
| `_form_input.html` | Styled input field with label, error state, and hint text | Expense form, setup wizard |
| `_button.html` | Primary, secondary, and danger button variants | All screens |
| `_badge.html` | Initials badge (paid-by), status badge (proposed/accepted/gift) | Expense feed, expense detail |
| `_balance_bar.html` | Red/green horizontal bar with names and amounts | Dashboard |
| `_date_header.html` | Day separator in expense feed | Expense feed |
| `_nav.html` | Consistent navigation — desktop header bar, mobile bottom bar | All screens |
| `_bottom_sheet.html` | Slide-up overlay for expense form on mobile | Mobile expense capture |
| `_step_indicator.html` | Settlement flow progress (step 1/2/3) | Settlement flow |
| `_empty_state.html` | Contextual empty state with guidance text and action | Dashboard, expense feed, settlement, registry |
| `_recurring_card.html` | Recurring cost definition card — icon, name, amount, frequency, normalized monthly cost, pause toggle | Registry view |
| `_recurring_widget.html` | Dashboard recurring cost summary — active count, monthly total, upcoming due dates | Dashboard |
| `_reminder_card.html` | Due-soon reminder card with "Create Expense" action | Dashboard |
| `_date_confirm_modal.html` | Compact modal for manual expense creation from recurring cost | Dashboard, registry |

Note: On desktop, the expense form is inline (no modal/bottom sheet needed). The `_bottom_sheet.html` partial is
mobile-only. These are different layout patterns, not the same component with different CSS.

**Visual Tone:**

- Card-based layouts with generous whitespace (`p-4`, `rounded-lg`, `shadow-sm`)
- Content-forward — minimal chrome, all visual weight on data (amounts, locations, balances)
- Warm primary accent color for navigation and interactive elements — feels like home, not like a bank
- Clean input styling — rounded borders, clear focus states, sufficient padding for touch targets
- Color used sparingly and purposefully: green/red for balance direction only, primary accent for actions and
  navigation, neutral for everything else
- Light background as default. No dark mode in MVP (can be added later via Tailwind's `dark:` variants)

## Customization Strategy

**Phase 1 (MVP1a):** Establish the base partials and design tokens. Build the expense card, form input, button,
navigation, and HTMX transition CSS first — these are used on every screen. Include the baseline HTMX swap transitions
(opacity fade) from day one. Visual polish is secondary to functional correctness, but the card-based visual tone is
established immediately.

**Phase 2 (MVP1b-c):** Add settlement-specific partials (step indicator, balance bar). Refine the expense card for
settlement review context (accept/discard controls). Ensure visual consistency across all screens.

**Phase 3 (MVP1d):** Polish pass — responsive refinements, enhanced HTMX transition animations, micro-interactions
(copy-to-clipboard feedback, form reset animation). Location typeahead client-side component (small vendored JS).

**Future (MVP2+):** If the app grows to need more components (event cards, participant lists, multi-person balance
bars), the pattern is established: create a Jinja2 partial, style with Tailwind, add to the component inventory. No
migration needed.
