# Glance Dashboard Integration

Cost Tracker can display your household's finances on a
[Glance Dashboard](https://github.com/glanceapp/glance) using the `custom-api` widget type.

Once configured, your Glance dashboard shows live data — current month spending, who owes
whom, and upcoming recurring costs — without logging into Cost Tracker.

## Prerequisites

- A running Glance instance
- Access to Cost Tracker's `GLANCE_API_KEY` environment variable (set by your admin)

## Set Up a Widget

### 1. Get Your API Key

Ask your Cost Tracker admin for the value of the `GLANCE_API_KEY` environment variable.
Store it as `COST_TRACKER_API_KEY` in your Glance environment (or secrets file).

### 2. Add the Widget to Your Glance Config

Paste one of the example configurations below into your Glance `glance.yaml` and adjust
the URL to match your Cost Tracker hostname.

### 3. Reload Glance

Glance picks up config changes on reload. Your widget appears with live data from Cost Tracker.

## Example Configurations

### Single Combined Widget

Shows month spending, balance, and upcoming recurring costs in one widget.

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

### Separate Widgets (Same Endpoint)

Split month summary and recurring costs into two focused widgets.
Glance caches responses, so both widgets share a single HTTP request within the cache window.

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

## Further Reading

For the full API field reference and gjson accessor details, see
[Glance Integration API Reference](../development/glance-integration.md).
