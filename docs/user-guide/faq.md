# FAQ

## General

### What is Cost Tracker?

A self-hosted app for partners or housemates to track shared expenses, calculate balances, and
settle up. You host it yourself — your data stays on your server.

### How is it different from Splitwise?

Splitwise is designed for one-off events (trips, dinners). Cost Tracker is designed for ongoing
shared living — continuous logging, monthly settlements, recurring costs. It's also self-hosted,
so you control your data.

### How many people can use it?

The app is designed for households — typically 2 people, but the data model supports multiple
members per group.

## Expenses

### Can I edit an expense after it's been settled?

No. Settled expenses are locked and cannot be edited, deleted, or have notes added. This ensures
the settlement record is accurate. If you made a mistake, create a new correcting expense.

### What happens if I mark an expense as a gift?

Gift expenses are excluded from balance calculations and settlements. Use this for costs that
shouldn't be split (e.g., one person treating the other).

### Do I have to split everything 50/50?

No. You can split expenses evenly, by shares (weighted), by percentage, or by exact amounts.
Each expense can use a different split type.

## Settlements

### Do I have to settle every month?

No. You can settle whenever you want — monthly, weekly, or whenever the balance gets large enough.
There's no automatic settlement.

### Does Cost Tracker transfer money?

No. Cost Tracker calculates who owes whom and records the settlement. You make the actual transfer
via your bank or payment app.

### Can I undo a settlement?

No. Settlements are permanent records. If there was a mistake, discuss it with your partner and
create a new expense to correct the difference.

## Recurring Costs

### What happens if I miss a recurring expense?

If auto-generate is enabled, missed expenses are created the next time auto-generation runs
(on login or via the daily cron job). Multiple missed periods will generate multiple expenses.

### Can I change the amount of a recurring cost?

Yes. Edit the recurring definition and future generated expenses will use the new amount.
Previously generated expenses are not affected.

## Self-Hosting

### What do I need to run Cost Tracker?

- A server or VPS with Docker
- PostgreSQL 18+
- An OIDC provider (Authentik, Keycloak, Auth0, etc.)

See the [Installation Guide](../operations/installation.md).

### Is there a hosted version?

No. Cost Tracker is designed to be self-hosted. There is no SaaS offering.

### How do I back up my data?

All data is in PostgreSQL. Use `pg_dump` for backups. See the
[Database Guide](../operations/database.md) for details.

### How do I update to a new version?

Pull the latest Docker image and run migrations. See the
[Upgrade Guide](../operations/upgrading.md).
