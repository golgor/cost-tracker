# Glance Dashboard Integration

The cost-tracker exposes a read-only JSON API at `/api/v1/summary` for
[Glance Dashboard](https://github.com/glanceapp/glance) `custom-api` widgets.

## Authentication

Set the `GLANCE_API_KEY` environment variable on the cost-tracker instance.
Glance sends it via `Authorization: Bearer <key>` header.

## Endpoint

**`GET /api/v1/summary`**

Query parameters:

| Param   | Default | Description                          |
|---------|---------|--------------------------------------|
| `limit` | 10      | Max upcoming recurring items (1-50)  |

### Example response

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
      }
    ]
  }
}
```

## Glance widget configuration

### Single combined widget

```yaml
- type: custom-api
  title: Cost Tracker
  url: https://costs.example.com/api/v1/summary
  headers:
    Authorization: Bearer ${COST_TRACKER_API_KEY}
  cache: 30m
  template: |
    <div>
      <p>This month: {{ .JSON.String "month.currency" }}{{ .JSON.String "month.total" }}
         ({{ .JSON.Int "month.expense_count" }} expenses)</p>
      <p>{{ .JSON.String "month.balance.direction" }}</p>
      <p>Recurring: {{ .JSON.Int "recurring.active_count" }} active,
         {{ .JSON.String "recurring.currency" }}{{ .JSON.String "recurring.total_monthly_cost" }}/mo</p>
      {{ range .JSON.Array "recurring.upcoming" }}
        <p>{{ .String "name" }} - {{ .String "amount" }} on {{ .String "next_due_date" }}</p>
      {{ end }}
    </div>
```

### Separate widgets (same endpoint, different templates)

Use multiple `custom-api` widgets pointing at the same URL. Glance caches
responses, so repeated calls to the same URL within the cache window are free.

```yaml
# Month summary widget
- type: custom-api
  title: Monthly Expenses
  url: https://costs.example.com/api/v1/summary
  headers:
    Authorization: Bearer ${COST_TRACKER_API_KEY}
  cache: 30m
  template: |
    <p>{{ .JSON.String "month.currency" }}{{ .JSON.String "month.total" }}
       ({{ .JSON.Int "month.expense_count" }} expenses)</p>
    <p>{{ .JSON.String "month.balance.direction" }}</p>

# Recurring costs widget
- type: custom-api
  title: Recurring Costs
  url: https://costs.example.com/api/v1/summary
  headers:
    Authorization: Bearer ${COST_TRACKER_API_KEY}
  cache: 1h
  template: |
    <p>{{ .JSON.Int "recurring.active_count" }} active,
       {{ .JSON.String "recurring.currency" }}{{ .JSON.String "recurring.total_monthly_cost" }}/mo</p>
    {{ range .JSON.Array "recurring.upcoming" }}
      <p>{{ .String "name" }} - {{ .String "amount" }} ({{ .String "next_due_date" }})</p>
    {{ end }}
```
