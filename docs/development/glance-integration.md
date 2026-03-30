# Glance Integration API Reference

Cost Tracker exposes a read-only JSON API for
[Glance Dashboard](https://github.com/glanceapp/glance) `custom-api` widgets.

Browse the auto-generated OpenAPI documentation at `/api/v1/docs` (Swagger UI)
or `/api/v1/redoc` (ReDoc).

## Authentication

Requests require a Bearer token in the `Authorization` header.
Configure the token via the `GLANCE_API_KEY` environment variable on the
cost-tracker instance.

```yaml
headers:
  Authorization: Bearer ${COST_TRACKER_API_KEY}
```

## Endpoint

### `GET /api/v1/summary`

Returns a combined summary of the household's finances: current month totals,
balance between partners, recurring cost overview, and upcoming scheduled items.

| Query param | Default | Description                         |
|-------------|---------|-------------------------------------|
| `limit`     | 10      | Max upcoming recurring items (1–50) |

## Response Schema

All money values are **strings** (e.g. `"123.45"`), never floats.
Dates are ISO 8601 date strings (`"YYYY-MM-DD"`) — not datetimes.

### Full Example Response

```json
{
  "month": {
    "period": "2026-03",
    "total": "1234.56",
    "currency": "EUR",
    "expense_count": 42,
    "unsettled_count": 15,
    "balance": {
      "net_amount": "50.00",
      "direction": "Alice owes Bob",
      "members": [
        {"name": "Alice", "net": "-50.00"},
        {"name": "Bob", "net": "50.00"}
      ]
    }
  },
  "recurring": {
    "active_count": 8,
    "total_monthly_cost": "456.78",
    "currency": "EUR",
    "upcoming": [
      {
        "name": "Netflix",
        "amount": "15.99",
        "next_due_date": "2026-04-01",
        "frequency": "monthly",
        "payer": "Alice"
      },
      {
        "name": "Spotify",
        "amount": "9.99",
        "next_due_date": "2026-04-15",
        "frequency": "monthly",
        "payer": "Bob"
      }
    ]
  }
}
```

## Field Reference

### `month` object

| Field             | Type   | Description                                                               |
|-------------------|--------|---------------------------------------------------------------------------|
| `period`          | string | Current month as `"YYYY-MM"`                                              |
| `total`           | string | Total spending this month (all statuses)                                  |
| `currency`        | string | Currency code (e.g. `"EUR"`)                                              |
| `expense_count`   | int    | Number of expenses this month                                             |
| `unsettled_count` | int    | Number of expenses not yet settled (across all time, not just this month) |
| `balance`         | object | Balance between partners (see below)                                      |

### `month.balance` object

| Field               | Type   | Description                                                               |
|---------------------|--------|---------------------------------------------------------------------------|
| `net_amount`        | string | Net amount owed (e.g. `"50.00"`)                                          |
| `direction`         | string | Direction: `"Alice owes Bob"` or `"All square"`                           |
| `members`           | array  | Per-member breakdown (see below)                                          |

### `month.balance.members[]` items

| Field  | Type   | Description                                                        |
|--------|--------|--------------------------------------------------------------------|
| `name` | string | Member's display name                                              |
| `net`  | string | Signed net balance: positive = owed money, negative = owes money   |

### `recurring` object

| Field                | Type   | Description                                            |
|----------------------|--------|--------------------------------------------------------|
| `active_count`       | int    | Number of active recurring cost definitions            |
| `total_monthly_cost` | string | Sum of all active definitions normalized to monthly    |
| `currency`           | string | Currency code                                          |
| `upcoming`           | array  | Next scheduled items, sorted by date (see below)       |

### `recurring.upcoming[]` items

| Field               | Type   | Description                                                               |
|---------------------|--------|---------------------------------------------------------------------------|
| `name`              | string | Name (e.g. `"Netflix"`)                                                   |
| `amount`            | string | Amount per occurrence                                                     |
| `next_due_date`     | string | Next date as `"YYYY-MM-DD"`                                               |
| `frequency`         | string | Frequency (e.g. `"monthly"`, `"yearly"`)                                  |
| `payer`             | string | Display name of the assigned payer                                        |

## Edge Cases

| Scenario               | Behavior                                                                     |
|------------------------|------------------------------------------------------------------------------|
| No group exists        | All values zero/empty, currency defaults to `"EUR"`                          |
| No expenses            | `total`: `"0.00"`, `expense_count`: 0, balance: All square                   |
| No recurring costs     | `active_count`: 0, `total_monthly_cost`: `"0.00"`, `upcoming`: `[]`          |
| Partners fully settled | `balance.direction`: `"All square"`, `net_amount`: `"0.00"`                  |

## gjson Accessor Cheat Sheet

For building Glance `custom-api` widget templates, these are the gjson paths
to access each field:

```text
month.period                        → "2026-03"
month.total                         → "1234.56"
month.currency                      → "EUR"
month.expense_count                 → 42
month.unsettled_count               → 15
month.balance.net_amount            → "50.00"
month.balance.direction             → "Alice owes Bob"
month.balance.members               → array (iterate with {{ range }})
month.balance.members.#             → member count (2)

recurring.active_count              → 8
recurring.total_monthly_cost        → "456.78"
recurring.currency                  → "EUR"
recurring.upcoming                  → array (iterate with {{ range }})
recurring.upcoming.#                → upcoming item count
```

### Accessor methods in Go templates

```text
.JSON.String "month.total"          → string value
.JSON.Int "month.expense_count"     → integer value
.JSON.Float "month.total"           → float (avoid for money display)
.JSON.Array "recurring.upcoming"    → iterable array
.JSON.Exists "month.balance"        → boolean check

Within {{ range .JSON.Array "..." }}:
  .String "name"                    → field from current array item
  .String "amount"                  → field from current array item
```
