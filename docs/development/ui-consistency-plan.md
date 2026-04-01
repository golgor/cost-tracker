# UI Consistency Plan

## Objective

Make page layout, button styling, and form controls consistent across Expenses,
Recurring, Trips, and Settlements while continuing to use Flowbite components.

## Standards

- Use shared page wrappers:
  - `ct-page-tight` for form-focused pages
  - `ct-page` for standard list/detail pages
  - `ct-page-wide` for the expenses dashboard layout
- Use shared action classes:
  - `ct-btn-primary` for primary actions
  - `ct-btn-secondary` for secondary actions
- Use shared form control class:
  - `ct-input` for base input/select visual consistency
- Keep navbar-to-content spacing controlled by `base.html` main padding.

## Rollout

1. Add shared classes in `app/static/src/input.css`.
2. Normalize base page padding in `app/templates/base.html`.
3. Migrate page wrappers and headers in:
   - `app/templates/expenses/index.html`
   - `app/templates/recurring/index.html`
   - `app/templates/trips/index.html`
   - `app/templates/settlements/*.html`
4. Replace one-off primary/secondary button class strings with shared button classes.
5. Ensure loading indicators in submit buttons do not affect label centering.

## Acceptance Criteria

- Primary buttons have the same color, typography, and padding across templates.
- Secondary buttons match each other across templates.
- Content starts at a consistent vertical offset under the navbar.
- No visible layout jump between similar page types.
- Loading spinner does not shift submit button text.
