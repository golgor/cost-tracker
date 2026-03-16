# Defining Core Experience

## Defining Experience

**"Log it in 15 seconds, settle it together in 10 minutes."**

Cost-tracker's defining experience is **managing shared spending as a natural household rhythm** — not splitting debts, not tracking who owes whom, but maintaining a shared picture of where money goes and squaring up together each month.

The mental model is a shared notebook, not a ledger. Users don't think "I need to log a debt" — they think "we spent money at Spar." The language, the flow, and the feel should reinforce this: *our expenses*, not *your debts*.

**Content design decision — the app's vocabulary:**

- **Use:** "shared expenses," "balance," "settle up," "our spending," "transfer"
- **Avoid:** "debt," "owe," "split" (in UI labels and copy — technical docs may still use "split mode" as a term of art)
- **Form context** speaks first person: "paid by Golgor," "I paid for this"
- **Dashboard context** speaks shared: "our balance," "shared expenses," "settle up"

This vocabulary distinction drives partial naming, label text, and copy decisions throughout implementation.

Two interactions define the product:

1. **Capture** — Amount, location, done. The expense goes into the shared pot. No friction, no ceremony. This is the reflex.
2. **Settlement** — Sit together, review the month, confirm it's fair, transfer, close the chapter. This is the ritual.

If capture is effortless, the data is complete. If settlement is trustworthy, the system earns its place. Everything else — the dashboard, the feed, the recurring costs — exists to connect these two moments.

## User Mental Model

**How users think about this task:**

These users are migrating from a broken system (home-automation-hub), not starting from zero. They've already internalized the rhythm of shared expense tracking — log expenses separately, review together periodically, settle via bank transfer. The mental model is established; the previous tool just failed on execution. This means they arrive with *stronger* opinions about what should work, because they've already experienced what doesn't: unclear labels, broken navigation flow (had to navigate to the expense list before adding), and a confusing UI that eroded Partner's confidence.

The mental model they bring is **household bookkeeping**: "we share expenses, we need to balance them out periodically." They don't think in terms of debt graphs, split ratios, or transaction histories. They think: "I paid for groceries, she paid for gas, at some point we figure out the difference."

**Expectations:**

- Adding an expense should feel as quick as making a mental note
- The balance should be immediately understandable — who owes, how much, one glance
- Settlement should be a conversation, not a spreadsheet exercise
- The system shouldn't require explanation — both users should be able to use it without a tutorial

**Frustration sources from the previous system:**

- Navigation confusion: "where do I click to add an expense?"
- Label ambiguity: buttons and fields that don't clearly say what they do
- Flow breaks: having to navigate to a list before you can add to it
- Lack of visual summary: no at-a-glance balance indicator

## Success Criteria

**Design targets for the core experience:**

(Note: these are design targets guiding UX decisions, not instrumented KPIs. MVP1 has no analytics — validation is qualitative through real usage.)

1. **"This just works"** — Users log expenses without consciously thinking about the interface. Amount, location, save. The interaction becomes muscle memory within the first week.

2. **"I know where we stand"** — Opening the dashboard instantly communicates the balance state. The balance bar imprints — users can close the app and still remember roughly what they owe or are owed. No mental math required.

3. **"We agree on the numbers"** — Settlement review produces zero surprises. Both partners look at the total, nod, and confirm. The process builds confidence, not anxiety.

4. **"That was painless"** — Monthly settlement takes under 15 minutes from start to bank transfer. The ceremony feels like closing a chapter, not doing homework.

5. **"I never get lost"** — At no point does either user wonder "where am I?" or "how do I do this?" Every screen has one obvious action. Navigation is consistent and labeled clearly.

**Design target indicators:**

- Expense capture completion: target >95% of started entries saved (form opens → saves)
- Average capture time: target under 30 seconds from app open to save
- Settlement completed in one sitting (no abandoned reviews)
- Zero "where do I click?" moments after the first session

## Novel UX Patterns

**Pattern analysis: Established patterns throughout.**

Cost-tracker does not require novel interaction design. The use case — log expenses, review balance, settle up — maps directly to proven patterns:

- **Expense entry** → standard form with smart defaults (Swish-inspired minimal input)
- **Expense feed** → chronological list with grouping and visual scanning aids (messaging app pattern)
- **Balance display** → color-coded horizontal bar (Spliit pattern)
- **Settlement flow** → guided multi-step review (Stripe Checkout pattern)
- **Navigation** → persistent nav with clear labels (standard web app)

**The innovation is in the removal of complexity, not the addition of novelty.** Where other expense-splitting apps add features (categories, budgets, receipt scanning, social features), cost-tracker strips down to the essential: capture and settle. The "new" thing is how little there is — and how well that little works.

No user education is needed beyond the first settlement walkthrough (which happens co-located, so one partner can guide the other). Every interaction uses patterns users already understand from other apps.

## Experience Mechanics

**Expense Capture (the daily reflex):**

**1. Initiation:**

- Mobile: FAB (floating action button) visible on every screen, large thumb-friendly target
- Desktop: "Add Expense" button in the toolbar, always visible
- No navigation required — the action is available from wherever the user is

**2. Interaction:**

- Amount field auto-focuses with numeric keyboard (`inputmode='decimal'` on mobile)
- User types amount → moves to location field (tap on mobile, tab on desktop)
- User types location (future: typeahead from previous locations)
- All other fields (split mode, paid-by, date, currency) pre-filled with smart defaults
- Optional: adjust any default before saving
- Real interaction count on mobile: tap FAB → type amount → tap location → type location → tap save (4-5 taps + 2 typing sessions). Feels fast because cognitive load is low, not because interaction count is minimal.

**3. Feedback:**

- Mobile: bottom sheet slides down, expense appears in feed behind it (self-confirming)
- Desktop: form clears and resets, new expense appears at top of feed
- Instant visual confirmation — no success banner needed when the result is visible
- On error: inline message on the field that failed, form stays open with data preserved

**4. Completion:**

- Mobile: bottom sheet dismisses, user is back where they started
- Desktop: form resets to empty state, cursor returns to amount field (ready for next entry)
- The expense is in the shared pot. Done. Move on.

---

**Settlement Review (the monthly ritual):**

**1. Initiation:**

- Tappable "Unsettled" count widget on the dashboard (navigates to settlement flow when count > 0)
- Desktop-only optimized flow (works on mobile, designed for desktop)
- Both partners co-located — Golgor drives, Partner follows on the same screen

**2. Interaction:**

- **Step 1 — Review:** All unsettled expenses displayed, grouped and scannable. Each expense pre-accepted by default (trust philosophy + fewer HTMX round-trips — most expenses stay accepted, minimizing server toggles). Users discard exceptions only. Live-updating settlement total reflects current selections.
- **Step 2 — Confirmation gate:** Summary screen showing final total, transfer direction ("Transfer €X from A to B"), and expense count. This is a read-and-confirm moment (like Stripe Checkout's "review your order"), not a separate interaction phase. One "Confirm Settlement" button.
- **Step 3 — Complete:** Success screen with reference ID prominently displayed, copy-to-clipboard button, transfer instructions. Visual "chapter closed" signal.

**3. Feedback:**

- Each accept/discard updates the running total immediately (HTMX partial swap)
- Progress indicator shows which step of the flow the user is on
- Numbers are always visible and always add up — transparency builds confidence

**4. Completion:**

- Reference ID copied, bank transfer initiated outside the app
- Settlement moves to history — browsable, auditable, a record of the shared financial life
- Dashboard balance resets. New chapter begins.
