# Visual Design Foundation

## Color System

**Palette philosophy: Warm, grounded, household — not corporate, not playful.**

The color system serves three purposes: warmth (this is a home tool), clarity (information hierarchy), and meaning (balance direction). Colors are defined as Tailwind design tokens in `tailwind.config.js`. All colors within the palette share warm undertones for temperature consistency.

**Primary Accent — Warm Terracotta/Clay**
- `primary-500`: A warm terracotta (~`#C27B5A`) — the main interactive color for buttons, active nav, links, FAB
- `primary-600`: Darker variant (~`#A8654A`) for hover states
- `primary-400`: Lighter variant for subtle highlights and active backgrounds
- `primary-50`: Very light wash (~`#FDF5F0`) for selected/active card backgrounds

This earthy tone feels domestic and warm without being childish. It stands out clearly against neutral backgrounds without the coldness of blue or the intensity of red.

**Settlement completion accent:** A warm amber shift (~`#D4913A`) for the "chapter closed" success moment — brighter and more celebratory than the standard terracotta, still in the warm earth family. Used only on the settlement completion screen (checkmark, success message).

**Neutral Palette — Warm Grays (Tailwind `stone` scale)**
- Use Tailwind's built-in `stone` palette as-is — it already has warm undertones that harmonize with the terracotta accent. No overrides needed.
- `stone-50` to `stone-100`: Page backgrounds, card surfaces
- `stone-200` to `stone-300`: Borders, dividers, inactive elements
- `stone-500` to `stone-600`: Secondary text, metadata, labels
- `stone-800` to `stone-900`: Primary text, headings

**Page background:** Barely warm off-white (~`#FAF8F6`) — warm enough to feel cohesive with terracotta, neutral enough that the accent stands out as intentional and distinctive. Not so warm it becomes an Instagram filter.

**Semantic Colors — Reserved and purposeful**
- **Balance green** (~`#2E7D5B` — warm forest/emerald, not mint/lime): "You are owed" side of the balance bar. Must lean warm to harmonize with the terracotta palette. Used exclusively for positive balance direction.
- **Balance red** (~`#B8453A` — warm brick/rust, not cherry/crimson): "You owe" side of the balance bar. Warm undertones to avoid a Christmas clash with the green. Used exclusively for negative balance direction.
- **Error red** (distinct from balance red — slightly different shade, always paired with explanatory text): Form validation errors, failed actions.
- **Success/confirmation**: Primary terracotta serves as the standard confirmation color. Settlement completion uses the warm amber variant. No separate green for "success" — avoids confusion with balance green.

**Paid-by badges:**
- Golgor: warm tone (muted clay/sand) — aligns with the primary palette, he's the system builder
- Partner: cooler contrast (dusty sage/muted teal) — visually distinct from the warm UI, stands out at feed-scanning speed
- Color distance between badges is the priority — they must be instantly distinguishable at scan speed, not semantically meaningful

**Color usage rules:**
- Green and red appear **only** in the balance bar and settlement totals — never for buttons, status badges, or general UI elements
- Primary terracotta is the only "branded" color — it appears on interactive elements (buttons, FAB, active nav, links)
- Background is warm off-white, cards are white — subtle depth without heavy shadows
- All colors in the palette share warm undertones for temperature consistency

**Tailwind config approach:**
```js
// tailwind.config.js — extend only what's custom
colors: {
  primary: {
    50: '#FDF5F0',
    // ... full scale
    500: '#C27B5A',
    600: '#A8654A',
  },
  surface: {
    bg: '#FAF8F6',     // warm off-white page background
    card: '#FFFFFF',    // card backgrounds
  },
  settle: '#D4913A',   // settlement completion amber
  balance: {
    pos: '#2E7D5B',    // owed (green)
    neg: '#B8453A',    // owes (red)
  }
}
// Use built-in `stone` palette for neutrals — no override needed
```

## Typography System

**Font: System font stack (no custom web font)**

```css
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
```

Rationale: Zero load time, already optimized per platform, universally readable. For a ~5-screen utility app used by two people, a custom font adds payload without meaningful brand benefit. The visual identity comes from color, spacing, and layout — not typeface. If a custom font is desired later, Inter is the natural choice.

**Type Scale:**

| Token | Size | Weight | Use |
|---|---|---|---|
| `text-2xl` / `text-3xl` | 24-30px | Bold | Amount display on expense cards, balance bar amount |
| `text-xl` | 20px | Semibold | Page headings, settlement total |
| `text-lg` | 18px | Medium | Section headings, location/merchant in expense feed |
| `text-base` | 16px | Regular | Body text, form labels, nav items |
| `text-sm` | 14px | Regular | Metadata (date, split mode, secondary info) |
| `text-xs` | 12px | Medium | Badges (paid-by initials), timestamps, helper text |

**Typography principles:**
- Amounts are always the largest text in their context — they're the primary data point
- Location/merchant is bold at `text-lg` — the primary scannable identifier in the feed
- Metadata is visually quieter (smaller, lighter color) — present but not competing
- Minimum touch-target text is `text-sm` (14px) — nothing smaller on interactive elements

## Spacing & Layout Foundation

**Base unit: 4px (Tailwind default)**

The spacing system uses Tailwind's default scale (`1` = 4px, `2` = 8px, `3` = 12px, `4` = 16px, `6` = 24px, `8` = 32px). No custom scale needed.

**Layout feel: Airy but purposeful — generous breathing room without wasted space.**

**Card spacing:**
- Card padding: `p-4` (16px) on mobile, `p-5` (20px) on desktop
- Card gap (between cards in a feed): `gap-3` (12px) — enough separation to distinguish items, tight enough to show 4-5 expenses without scrolling on mobile
- Card border-radius: `rounded-lg` (8px) — modern without being bubbly

**Form spacing:**
- Field gap: `gap-4` (16px) between form fields — clear separation without feeling like a long form
- Input padding: `px-3 py-2.5` (12px/10px) — comfortable touch targets, not cramped
- Label-to-input gap: `gap-1.5` (6px) — tight association between label and field

**Page layout:**
- Page padding: `px-4` (16px) on mobile, `px-6` to `px-8` (24-32px) on desktop
- Section gap: `gap-6` (24px) between major sections (e.g., balance bar to expense feed)
- Max content width: `max-w-2xl` (672px) centered on desktop for single-column views (dashboard, expense feed). `max-w-3xl` (768px) for settlement review and any layout where the inline form sits alongside the feed. Test at implementation — 672px may feel tight for expense cards with all metadata visible.

**Feed layout:**
- Date headers get extra top margin (`mt-6`) to create clear visual groups
- Expense cards within a date group are tighter (`gap-2` or `gap-3`)
- The feed scrolls naturally — no fixed-height containers or virtual scrolling needed for the expected data volume

**Responsive approach:**
- Mobile-first CSS: base styles target phone, `sm:` and `md:` breakpoints add desktop adjustments
- No breakpoint below `sm` (640px) — modern phones are wide enough for the card layout
- Desktop breakpoint (`md:` 768px+) triggers: wider page padding, inline form layout (vs. bottom sheet), horizontal nav bar (vs. bottom nav)

## Accessibility Considerations

**Contrast:**
- All text meets WCAG AA contrast ratio (4.5:1 for body text, 3:1 for large text)
- Terracotta primary must be tested against both white card backgrounds and warm off-white page backgrounds — earthy tones can fail contrast checks if too light
- Balance bar green/red chosen for sufficient contrast, and the bar always includes text labels (names + amounts) — color is never the sole information carrier

**Touch targets:**
- Minimum 44x44px touch target on all interactive elements (buttons, form fields, nav items, FAB)
- FAB: 56px diameter minimum — prominent and thumb-reachable
- Expense cards in the feed: full card is tappable (if edit/detail is needed), not just a small icon

**Motion:**
- HTMX swap transitions kept to 150ms — fast enough to not delay interaction, slow enough to prevent flash
- `prefers-reduced-motion` media query respected: transitions disabled entirely for users who prefer it
- No auto-playing animations, no parallax, no decorative motion

**Focus states:**
- Visible focus ring on all interactive elements (Tailwind's `ring` utilities) — critical for desktop keyboard navigation during batch entry
- Focus ring uses primary accent color for consistency
- Tab order follows visual order — no `tabindex` hacks
