# Getting Started

A walkthrough of your first session with Cost Tracker — from login to your first expense.

## First Login

1. Navigate to your Cost Tracker instance (e.g., `https://costs.example.com`)
2. You'll be redirected to your OIDC provider (Authentik or similar) to log in
3. After authenticating, you're redirected back to Cost Tracker

Your account is automatically provisioned from your OIDC profile (display name and email).
After login, you land directly on the expenses page.

## Adding Your First Expense

<!-- TODO: Add screenshot of capture form -->

1. Tap the **+** button (mobile) or click **Add Expense** (desktop)
2. Fill in the details:
   - **Amount** — how much was spent
   - **Description** — what was it for (e.g., "Spar Groceries")
   - **Date** — defaults to today
   - **Paid by** — who actually paid
   - **Split type** — how to divide the cost (defaults to even)
3. A **split preview** shows how the expense will be divided before you confirm
4. Click **Create** — the expense appears in your feed

That's it. Your balance updates automatically.

## Inviting Your Partner

Your partner just logs in via the same OIDC provider. Their account is auto-provisioned and
they see the same shared expenses. No invite codes or manual setup needed. The `MAX_USERS`
setting (default 2) limits how many users can be created.

## Day-to-Day Usage

### Mobile (on-the-go logging)

The capture form is optimized for quick entry on a phone. The goal is 30 seconds or less:
amount, description, tap create. The payer defaults to you and the split defaults to even.

### Desktop (batch entry)

For entering multiple expenses at once (e.g., a week's worth of receipts), the desktop layout
is optimized for keyboard navigation. Tab through fields, enter amounts, and submit without
reaching for the mouse.

## What's Next

- [Features](features.md) — Detailed walkthrough of expenses, settlements, and recurring costs
- [FAQ](faq.md) — Common questions
