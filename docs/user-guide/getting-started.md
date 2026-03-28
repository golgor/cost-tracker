# Getting Started

A walkthrough of your first session with Cost Tracker — from login to your first expense.

## First Login

1. Navigate to your Cost Tracker instance (e.g., `https://costs.example.com`)
2. You'll be redirected to your OIDC provider (Authentik or similar) to log in
3. After authenticating, you're redirected back to Cost Tracker

The **first user** to log in is automatically made an admin. Subsequent users are added as regular
members.

## Setup Wizard

On your first login, you'll walk through a three-step setup:

### Step 1: Confirm Your Profile

Your display name and email are pulled from your OIDC provider. Confirm they look correct.

### Step 2: Create Your Household

Give your household a name (e.g., "Home", "Our Place"). This is the group that expenses are
tracked under.

### Step 3: Configure Defaults

- **Currency** — select your household currency (EUR, USD, GBP, SEK, NOK, DKK, CHF)
- **Default split** — how expenses are divided by default (even split)
- **Tracking threshold** — how many days of expenses to include in balance calculations
  (default: 365 days)

After completing setup, you'll land on the main expenses page.

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

When your partner logs in via the same OIDC provider, they are automatically added to your
household. No invite codes or manual setup needed — the first admin's group becomes the default
group for new users.

## Day-to-Day Usage

### Mobile (on-the-go logging)

The capture form is optimized for quick entry on a phone. The goal is 30 seconds or less:
amount, description, tap create. The payer defaults to you and the split defaults to even.

### Desktop (batch entry)

For entering multiple expenses at once (e.g., a week's worth of receipts), the desktop layout
is optimized for keyboard navigation. Tab through fields, enter amounts, and submit without
reaching for the mouse.

## What's Next

- [Features](features.md) — Detailed walkthrough of expenses, settlements, recurring costs,
  and admin features
- [FAQ](faq.md) — Common questions
