# UX Tasks: Trips Feature (MVP2)

This document outlines the design and mockup tasks for the @[conversation:"UX"] lead regarding the new Trips feature.

## Architecture Context
We have decided on a **Shared Magic Link + Cookie State** for guests, and a **Global Address Book** for Admins to manage guests. Guest identity is verified by tapping their name from a list, which sets a session cookie. Guests are backed by actual `Participant` IDs in the `trip_participants` table, and the QR code generation is handled server-side in Python.

---

## Required Views, Mockups, and HTMX Translation Maps

Below are the 7 core views modeled through Excalidraw-style image embeds where available, and textual wireframes for the new additions. The structural mapping to Jinja/HTMX partials is provided for the developers.

### 1. Admin Views

#### 1. Trip Dashboard
The main list of active and historical trips. This will live in the main navigation (e.g., inserted symmetrically between Expenses and Recurring).

![Admin Trips Dashboard](/home/golgor/.gemini/antigravity/brain/5b6793cd-d23b-47a9-a158-5d908ed4660e/admin_trips_view_1774987455997.png)

**HTMX / Template Mapping:**
- `app/templates/trips/index.html` (Extends `base.html` and hooks into Household Navigation)
- `app/templates/trips/_trip_list.html` (The `hx-get` target for refreshing the outer list)
- `app/templates/trips/_trip_card.html` (The individual loop component)

#### 2. Create/Edit Trip Modal
Needs fields for Trip Name, Currency, and a multi-select component for Participants. Includes a way to "Add New Guest".

![Create/Edit Trip Modal](/home/golgor/.gemini/antigravity/brain/85a7f571-0d53-465f-a14a-9c0208a25ad7/admin_trip_modal_1774990331425.png)

**HTMX / Template Mapping:**
- `app/templates/trips/_create_trip_modal.html` 
- Rendered in a standard `<dialog>` tag. Form uses `hx-post="/trips"` targeting the `#trip-list` to prepend the new trip upon success and closes the modal.
- The "Add New Guest" button can `hx-post` an inline addition to the address book, avoiding full page refreshes.

#### 3. Admin Trip Details
The feed of expenses for a specific trip, with share and settle actions.

![Admin Trip Details](/home/golgor/.gemini/antigravity/brain/85a7f571-0d53-465f-a14a-9c0208a25ad7/admin_trip_details_1774990348360.png)

**HTMX / Template Mapping:**
- `app/templates/trips/admin_detail.html` (Extends `base.html`)
- `app/templates/trips/_admin_expense_feed.html`
- The `[Share QR Link]` button triggers `app/templates/trips/_share_qr_modal.html`, where the QR code SVG/PNG (compiled server-side via Python) is embedded.

---

### 2. Guest Views (Mobile-First Focus)

*Critical Note: Guest views CANNOT extend `base.html` as it exposes Household Admin navigation. They must extend a new `guest_base.html` sandbox.*

#### 4. Guest Identity Selection (Who are you?)
The landing screen after scanning the shared QR code. Must list the trip's participants.

![Guest Identity Selection](/home/golgor/.gemini/antigravity/brain/85a7f571-0d53-465f-a14a-9c0208a25ad7/guest_identity_selection_1774990362283.png)

**HTMX / Template Mapping:**
- `app/templates/trips/guest_identify.html` (Extends `guest_base.html`)
- The buttons map to a simple `hx-post="/trips/{id}/identify"` that passes the `Participant` ID, sets a secure HTTP-only signed cookie, and redirects to the Summary view.

#### 5. Guest Trip Summary
The main view for a guest once identified.

![Guest Trip Summary View](/home/golgor/.gemini/antigravity/brain/5b6793cd-d23b-47a9-a158-5d908ed4660e/guest_trip_view_1774987769682.png)

**HTMX / Template Mapping:**
- `app/templates/trips/guest_summary.html` (Extends `guest_base.html`)
- Top contextual header includes: "Hello, Alice. `<a href="/trips/guest/logout">Not Alice?</a>`" to clear cookies.
- Huge bottom FAB toggles `_guest_expense_form.html`.
- `app/templates/trips/_guest_expense_feed.html` loaded as an independent partial.

#### 6. Guest Add Expense Form
Optimized for one-handed mobile entry.

![Guest Add Expense Screen](/home/golgor/.gemini/antigravity/brain/5b6793cd-d23b-47a9-a158-5d908ed4660e/guest_expense_view_1774987470304.png)

**HTMX / Template Mapping:**
- `app/templates/trips/_guest_expense_form.html`
- A mobile `<dialog>` bottom-sheet. Form POSTs to `/trips/{id}/expenses`, swaps the main feed, and resets itself for swift continuous entry.

#### 7. Guest Settlement/Balances View
Read-only view showing "Who owes Who" instructions.

![Guest Balances View](/home/golgor/.gemini/antigravity/brain/85a7f571-0d53-465f-a14a-9c0208a25ad7/guest_balances_view_1774990376147.png)

**HTMX / Template Mapping:**
- `app/templates/trips/guest_balances.html` (Extends `guest_base.html`)
- Injects standard `app/domain/balance.py` output cleanly mapped to HTML lists, filtered to specifically emphasize the logged-in Guest's obligations and incomings in priority. Use existing #2E7D5B (Green) and #B8453A (Red) hex tokens defined in our Visual Design Foundation.
