# Recurring Costs — Improvements Design

**Date:** 2026-03-31  
**Status:** Approved  
**Scope:** Improve the `/recurring` page with better card design, filter chips, an improved summary bar, and a "Make Personal" shortcut in the form.

---

## Problem

The recurring costs page is functional but limited:

- Cards are visually flat — no quick visual differentiation between categories or types
- Setting up a personal recurring cost (gym membership, personal subscription) requires 5 manual steps through the split config UI
- The summary bar only shows a total count and monthly cost — no per-person breakdown
- There is no way to filter by personal vs shared, by category, or by who pays

---

## Goals

1. Redesigned cards — color-accented left border per category, footer divider separating info from actions, split amounts and full due date visible
2. Filter chips — filter by shared/personal, who pays, and category; filters update the list and summary via HTMX
3. Stats grid summary bar — shared/mo, personal/mo, total/mo with per-person sub-lines
4. "Make Personal" toggle in the recurring form — one click to configure a 100% personal cost

---

## What Is "Personal"

A recurring cost is **personal** when one person bears 100% of the normalized monthly cost. This is derived from existing domain fields — no new database column is needed.

Detection logic (in `RecurringDefinitionViewModel.from_domain()`):

- `split_type == PERCENTAGE` and one user's config value is `"0"` → personal
- `split_type == SHARES` and one user's config value is `"0"` → personal
- `split_type == EXACT` and one user's config value is `"0.00"` → personal

`is_personal` is a computed view model field. Existing recurring costs configured manually as 100%/0% will automatically show the personal badge without any migration.

---

## Section 1: View Model Changes

`RecurringDefinitionViewModel` gains three new fields:

| Field | Type | Description |
|---|---|---|
| `is_personal` | `bool` | True when one user bears 100% of the cost |
| `personal_owner_id` | `int \| None` | User ID of the sole payer (for filtering) |
| `per_person_monthly_cost` | `dict[int, Decimal]` | Maps user_id → normalized monthly share |

All three are computed in `from_domain()` from existing `split_type`, `split_config`, `amount`, `frequency`, and `interval_months`. No new DB fields.

`from_domain()` gains a `member_ids: list[int]` parameter so it can compute each user's share. The caller (route or `_to_view_models`) passes the full household member list.

`get_registry_summary` is extended to return:

| Field | Type | Description |
|---|---|---|
| `shared_monthly_total` | `Decimal` | Sum of normalized monthly cost of shared definitions |
| `personal_monthly_totals` | `dict[int, Decimal]` | Per-user sum of personal costs |
| `per_person_shared_cost` | `dict[int, Decimal]` | Each user's share of shared costs |

---

## Section 2: Filter Endpoint

New HTMX endpoint: `GET /recurring/filtered`

Query parameters:
- `scope: str` — `all` | `shared` | `personal` (default: `all`)
- `payer_id: int | None` — filter by who pays
- `category: str | None` — filter by category
- `tab: str` — `active` | `paused` (default: `active`, preserves tab state)

Returns the `#definition-list` partial: updated summary bar + filtered card list.

A new `get_filtered_definitions(session, scope, payer_id, category, active_only)` query function is added to `recurring_queries.py`, following the same pattern as `get_filtered_expenses`. The existing `/recurring/tab/{tab}` endpoint is unchanged.

Filters and tabs are independent — "Paused + Personal" is a valid combination.

---

## Section 3: Card Template

`_definition_card.html` is rewritten:

**Structure:**
```
┌─[color bar]─────────────────────────────────────────┐
│  Name  [auto] [personal]           €XX.XX/mo         │
│  €X.XX / frequency · [A] pays · Split     €X.XX/pers │
│  [R: €X/mo] [A: €X/mo]  ← non-EVEN splits only      │
│  Due: Apr 12, 2026  ← always includes year           │
├──────────────────────────────────────────────────────┤
│  category label         [Create] [Edit] [Pause] [Del]│
└──────────────────────────────────────────────────────┘
```

**Left border color by category:**

| Category | Color |
|---|---|
| subscription | indigo (#6366f1) |
| insurance | amber (#f59e0b) |
| membership | pink (#ec4899) |
| utilities | green (#10b981) |
| childcare | sky (#0ea5e9) |
| other / none | stone (#a8a29e) |

**Badge logic:**
- `[auto]` — shown when `is_auto_generate`
- `[personal]` — shown when `is_personal`
- `[paused]` — shown when `not is_active`

**Split display:**
- EVEN split: shows `€X.XX/person` on the right
- Non-EVEN split: shows per-person normalized monthly pills (e.g. `R: €10/mo`, `A: €10/mo`)

**Due date:** always formatted as `Mon DD, YYYY` (e.g. `Jan 15, 2027`) to avoid confusion for yearly/quarterly recurring costs.

---

## Section 4: Summary Bar

`_summary_bar.html` is rewritten to a stats grid:

```
┌──────────────────────────────────────────────────────┐
│  SHARED /MO        PERSONAL /MO       TOTAL /MO       │
│  €103.99           €35.00             €138.99          │
│  R: €49.50 · A: €54.50  R: €35.00 · A: €0  4 costs  │
└──────────────────────────────────────────────────────┘
```

The summary updates together with the card list when filters are active (both are returned by `/recurring/filtered`).

---

## Section 5: Filter Chips

Filter chips are added above `#definition-list` in `index.html`:

```
[All]  [Shared]  [Personal]  [R pays]  [A pays]  [Subscription]  [Insurance]  …
```

Each chip uses `hx-get="/recurring/filtered"` with the appropriate query params and `hx-target="#definition-list"`. Active chip is highlighted. Category chips are only shown for categories that have at least one active definition.

The route passes `active_categories: list[str]` to the template — computed from the full unfiltered definition list so the chip bar doesn't change as filters are applied.

---

## Section 6: "Make Personal" Toggle in Form

A toggle button is added to `form.html` above the split method section:

- **Default state:** button reads "Make Personal"
- **Active state:** button reads "Undo — make shared", split fields hidden, payer locked to current user

On click (JS only, no backend):
1. Sets `split_type` select to `PERCENTAGE` (hidden)
2. Sets `split_config` hidden input to `{"current_user_id": "100", "partner_id": "0"}`
3. Replaces `payer_id` dropdown with static text showing current user's name
4. Hides the split fields section
5. Toggles button label

On "Undo":
1. Resets `split_type` to `EVEN`
2. Clears `split_config`
3. Restores `payer_id` dropdown
4. Shows split fields section

If editing an existing personal recurring, the toggle is pre-activated. The edit form route computes `is_personal_edit: bool` from the existing definition's `split_type` and `split_config` (same logic as the view model) and passes it to the template context. The template uses this to render the button in its active state and hide the split fields on page load.

The current user's ID and the partner's ID are already available in the template context (`user.id`, `members` list).

---

## Testing Strategy

- **View model:** Unit tests for `is_personal`, `personal_owner_id`, `per_person_monthly_cost` across all split types
- **Summary query:** Unit tests for shared/personal/total breakdowns
- **Filter endpoint:** Integration tests for each filter combination (`scope`, `payer_id`, `category`, tab)
- **Card template:** Snapshot/content tests asserting badge presence, due date format, split pills
- **Form toggle:** Not directly tested (pure JS); covered by the existing form submission tests which validate the resulting `split_config`

---

## Out of Scope

- Glance dashboard API changes
- Admin/split type configuration via UI (separate initiative)
- Any new database columns or migrations
- Recurring cost history or audit trail
