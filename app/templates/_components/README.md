# Template Component Library

This directory contains reusable Jinja2 template components used throughout the cost-tracker application.

## Component Organization

Each component file is a Jinja2 include template prefixed with underscore (e.g., `_button.html`, `_badge.html`). Components are **presentation-only** — they handle HTML structure and styling, not business logic.

## Using Components

Components are included via Jinja2's `{% include %}` tag with context parameters:

```jinja2
{% set button_text = "Click me" %}
{% set button_variant = "primary" %}
{% include "_components/_button.html" %}
```

Or with inline context dict:

```jinja2
{% include "_components/_button.html" with {"label": "Save", "variant": "primary"} %}
```

## Component Design Principles

1. **Presentation-Only**: No business logic, no conditional branching based on application state
2. **Parameterized**: Accept 5-7 parameters max for customization; beyond that, create a variant component
3. **Accessible**: Always include semantic HTML, ARIA labels, and focus management
4. **Documented**: Every component has a header comment explaining purpose, parameters, and usage examples
5. **Extendable**: All components support `extra_class` parameter for one-off Tailwind class additions

## Components

- `_button.html` — Interactive buttons with variants (primary, secondary, danger)
- `_form_input.html` — Form field wrapper (text, email, select, textarea) with labels, errors, help text
- `_tab_nav.html` — Horizontal navigation tabs with active state
- `_filter_tabs.html` — Filter button group with active state
- `_badge.html` — Status/action badges with color variants and text indicators
- `_modal.html` — Confirmation dialogs with title, message, and action buttons
- `_alert.html` — Messages (error, success, info) with icons and dismiss buttons
- `_step_indicator.html` — Setup wizard progress indicator (step circles, completed checkmarks)
- `_setup_nav_buttons.html` — Two-button footer (back link + forward button/submit)

## Extension Patterns

When customizing a component:

1. **First choice**: Use component as-is (no changes needed)
2. **Second choice**: Add a variant parameter option (if repeatable pattern detected)
3. **Third choice**: Use `extra_class` for one-off Tailwind utilities
4. **Last resort**: Create a new variant component

**Example**: If you need a "destructive" button that's different from danger variant, either:
- Add variant option to `_button.html` (preferred if used 2+ times)
- Pass `extra_class="border border-red-600"` (one-off workaround)
- Create `_button_destructive.html` (if complex or used many times)

### Tailwind Class Collision Warning

**Avoid**: Passing incompatible classes via `extra_class` (e.g., `bg-red-500` when component already has `bg-blue-600`). CSS specificity will create unexpected results.

### Semantic HTML & Accessibility

All components must include:
- Semantic HTML tags (not just divs)
- ARIA labels and roles where needed (aria-label, role="button", aria-describedby, etc.)
- Focus management (tabindex, focus-ring Tailwind classes)
- Color-independent indicators (badges use text + icon, not color-only)
- Touch targets ≥44px minimum

## Testing

Components are tested via:
- **Architectural test**: `tests/architecture_test.py::test_templates_contain_no_complex_business_logic()`
- **Visual regression**: Screenshots before/after refactoring stored in `tests/visual/baselines/`
- **Integration tests**: HTMX form submissions and modal interactions tested in `tests/web/admin_ui_test.py`

## Component Inventory

See `docs/templates/component-inventory.md` for a complete mapping of every component and which files use it.

## Adding New Components

Before creating a new component:

1. Check `component-inventory.md` — is the pattern already extracted elsewhere?
2. Ask: "Is this used 2+ times?" If not, keep it inline (avoid premature extraction)
3. If extracting: limit parameters to 5-7 max; if more needed, design a variant
4. Add header documentation explaining purpose, required/optional parameters, and usage examples
5. Include semantic HTML + accessibility features from day one
6. Test visually in browser + ensure no HTMX interactions break
7. Update `component-inventory.md` post-implementation
