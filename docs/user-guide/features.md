# Features

A walkthrough of everything Cost Tracker can do.

## Expenses

The main screen shows your expense feed — a list of all shared expenses, most recent first.

TODO: Add screenshot of expense list

### Creating an Expense

Tap **+** (mobile) or **Add Expense** (desktop) to open the capture form:

- **Amount** — the total cost
- **Description** — a short label (e.g., "ICA", "Electric bill", "Dinner at Pasta Palace")
- **Date** — when the expense occurred (defaults to today)
- **Paid by** — which partner actually paid
- **Split type** — how the cost is shared:
  - **Even** — split equally between both partners
  - **Shares** — weighted split (e.g., one person gets 2 shares, another gets 1)
  - **Percentage** — each person pays a percentage (must total 100%)
  - **Exact** — specify exact amounts per person (must total the expense amount)

A **split preview** updates in real-time as you fill in the form, showing exactly how much each
person will owe.

### Viewing and Expanding Expenses

Each expense in the feed shows the description, amount, who paid, and date. Tap or click an
expense to expand it and see:

- Full split breakdown (who owes what)
- Who created the expense
- Notes and comments

### Editing an Expense

Open an expense and click **Edit** to change the amount, description, date, payer, or split type.

Settled expenses cannot be edited — they are locked as part of the settlement record.

### Deleting an Expense

Open an expense and click **Delete**. A confirmation dialog appears before the expense is removed.

Settled expenses cannot be deleted.

### Notes

Add notes to any pending expense for context or discussion (e.g., "Split differently because
I didn't eat" or "Receipt attached to fridge"). Only the note author can edit their notes.

### Filtering and Searching

<!-- TODO: Add screenshot of filter bar -->

The filter bar at the top of the expense list lets you narrow results:

- **Search** — filter by description text
- **Date range** — show expenses within a specific period
- **Paid by** — show only expenses paid by a specific person

Filters also affect the balance display, so you can see the balance for any time period.

### Marking as Gift

Expenses can be marked as a **gift**, which excludes them from balance calculations and
settlements. Use this for one-sided costs that don't need to be split (e.g., birthday presents).

## Balance

<!-- TODO: Add screenshot of balance bar -->

The balance bar at the top of the expenses page shows who owes whom and how much. It updates
automatically as expenses are added, edited, or deleted.

- **"All square!"** — the balance is zero
- **"Partner owes you €X"** — they owe you money
- **"You owe Partner €X"** — you owe them money

The balance only includes **pending** expenses — gifts and settled expenses are excluded.

## Settlements

Settlements are how you formally close out shared expenses and record the transfer.

<!-- TODO: Add screenshot of settlement review -->

### Settlement Flow

1. **Review** — navigate to Settlements and review all pending expenses. Select which expenses
   to include in this settlement (typically all of them).

2. **Calculate** — the app calculates the net balance: who owes whom, and how much. Transactions
   are minimized (e.g., if Alice owes Bob €50 and Bob owes Alice €20, the settlement is just
   Alice pays Bob €30).

3. **Confirm** — review the final transaction summary. This is your last chance to make changes
   before locking the expenses.

4. **Settle** — confirm the settlement. All included expenses are marked as settled (immutable).
   A settlement record is created with a reference ID.

5. **Transfer** — make the actual bank transfer for the calculated amount. Cost Tracker records
   the settlement but does not handle the payment itself.

### Settlement History

Browse past settlements to see:

- Date of settlement
- Number of expenses included
- Total amount transferred
- Transaction details (who paid whom)

Drill into any settlement to see the full list of expenses that were part of it.

## Recurring Costs

For expenses that repeat on a schedule — rent, subscriptions, insurance, utilities.

<!-- TODO: Add screenshot of recurring registry -->

### Creating a Recurring Cost

Navigate to **Recurring** and click **New**:

- **Name** — what this recurring cost is (e.g., "Rent", "Netflix", "Car Insurance")
- **Amount** — the recurring amount
- **Frequency** — how often it recurs:
  - Monthly
  - Quarterly
  - Semi-annually
  - Yearly
  - Every N months (custom interval)
- **Next due date** — when the next expense should be created
- **Paid by** — who pays this cost
- **Split type** — how to divide it
- **Category** — optional label (subscription, insurance, childcare, utilities, membership, other)
- **Auto-generate** — if enabled, the expense is created automatically when due

### Managing Recurring Costs

The recurring registry has two tabs:

- **Active** — currently enabled recurring costs, showing name, amount, frequency, and next
  due date
- **Paused** — temporarily disabled items

You can:

- **Edit** any recurring cost to change its settings
- **Pause** a recurring cost to temporarily stop generation (without deleting it)
- **Resume** a paused cost
- **Delete** a recurring cost (soft-delete — moved to paused)
- **Create expense now** — manually generate an expense for the current billing period

### Auto-Generation

When auto-generate is enabled, expenses are created automatically when due:

- Triggered on user login (best-effort)
- Triggered by a daily cron job (if configured)
- The next due date advances automatically after each generation
