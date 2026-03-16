# Desired Emotional Response

## Primary Emotional Goals

**Confidence** — The overriding emotional goal. Users must trust the system completely — that the numbers are correct,
that nothing was missed, that the settlement is fair. Without confidence, the app fails regardless of how fast or pretty
it is. Confidence is built through transparency (show the math), consistency (same behavior every time), and correctness
(the system catches mistakes before they matter).

**Effortlessness** — Expense capture should feel like jotting a note, not filing a form. The app gets out of the way.
When the interaction is over, the user shouldn't feel like they "used an app" — they should feel like they simply noted
something down. The cognitive load of tracking shared expenses should approach zero.

**Clarity** — The opposite of Partner's old frustration. Every screen answers three questions instantly: where am I,
what can I do, and what just happened. No ambiguity, no hunting, no "wait, what did that button do?" Clarity isn't just
visual — it's structural. The app has a small, obvious surface area.

**Closure** — Monthly settlement should feel like finishing a chapter. The review, the confirmation, the reference ID —
this is a ritual that produces satisfaction. Both partners walk away feeling "that's handled." The emotional payoff of
settlement is what makes the daily logging feel worthwhile.

## Emotional Journey Mapping

| Moment | Desired Feeling | Anti-feeling to Avoid |
|---|---|---|
| Opening the app (daily capture) | Familiar, quick — like picking up a pen | Dread, "ugh, I have to log this" |
| Adding an expense | Effortless, reflexive — done before you think about it | Tedious, form-filling, bureaucratic |
| Opening the dashboard (check-in) | Informed, in control — the picture sticks in a glance | Overwhelmed, confused by too much data |
| Scanning the expense feed | Recognition, shared awareness — "I see what we've been spending" | Suspicion, "what is this charge?" |
| Starting settlement review | Purposeful, collaborative — "let's do this together" | Anxious, "I hope the numbers are right" |
| Reviewing individual expenses | Confident, thorough — "yes, I remember this" | Doubtful, "should I accept something I don't recognize?" |
| Confirming settlement | Satisfaction, closure — a chapter closed | Uncertainty, "did that work? Is it done?" |
| Copying reference ID | Efficient, almost fun — the finishing touch | Annoyed, "why can't I just copy this?" |
| Returning after a week away | Welcome, caught up quickly — "I know where things stand" | Lost, "what happened while I was away?" |
| Something goes wrong (error, mistake) | Forgiven, guided — "easy, let's fix that" | Punished, anxious, "did I break something?" |

## Micro-Emotions

**Critical emotional states for cost-tracker:**

- **Confidence over skepticism** — The most critical axis. Every design choice should build confidence. Transparent
  calculations, visible audit trails, consistent behavior. Skepticism is the death of this product.
- **Collaboration over transaction** — The app mediates money between partners, which can feel transactional or even
  adversarial. The emotional register should feel like a shared space ("our expenses") not a ledger ("you owe me").
  Neutral transfer instructions ("Transfer X from A to B") over accusatory framing ("A owes B").
- **Forgiveness over punishment** — When users make mistakes (wrong amount, duplicate entry, accidental delete), the app
  should make correction easy and judgment-free. Undo is available. Errors are fixable. The audit trail is for
  transparency, not accountability.
- **Accomplishment over obligation** — Settlement should feel like a small win, not a chore. The monthly ritual is a
  moment of "we handled our finances well" not "we finally got around to this."

## Design Implications

| Emotional Goal | UX Approach |
|---|---|
| Confidence | Balance bar with names + amounts (always visible, always correct). Live-updating settlement total during review. Split validation that catches errors before save. Settlement history as proof that past settlements were handled correctly. |
| Effortlessness | Amount + location as the only perceived requirements. Smart defaults that make 90% of expenses a 2-field interaction. Form reset after save for batch flow. FAB always reachable on mobile. |
| Clarity | Date headers in expense feed for orientation. Paid-by badges for instant recognition. One primary action per screen. Consistent navigation across all views. Descriptive labels on options ("Split: Even") instead of icons or abbreviations. |
| Closure | Settlement confirmation with a visually conclusive moment (not just a flash message). Reference ID prominently displayed and one-click copyable. Settlement moves to history — visible, browsable, a record of the shared financial relationship. |
| Collaboration | Shared view (same data for both users). Neutral balance language ("Transfer X from A to B"). Both names on the balance bar. Expense feed shows who paid without judgment — just information. |
| Forgiveness | Inline error messages that explain what to fix, not just what went wrong. Easy correction of unsettled expenses. Undo capability during settlement review (re-accept after discard). No destructive actions without clear confirmation. |

## Emotional Design Principles

1. **Trust is earned in the details** — Rounding that always sums correctly. Split validation that never lets bad data
   through. Settlement totals that match the math. These aren't features — they're the foundation of the emotional
   relationship between user and product.

2. **Shared space, not score-keeping** — The app tracks expenses between partners, not debts between adversaries.
   Language, layout, and interaction design should reinforce that this is a collaborative tool for a shared life, not a
   mechanism for enforcing fairness.

3. **Errors are conversations, not dead ends** — When something goes wrong, the app says "here's what happened, here's
   how to fix it" — not "invalid input." Error states are designed with the same care as success states. The tone is
   helpful, not clinical.

4. **The payoff is in the ritual** — The monthly settlement is the emotional anchor of the product. It should feel like
   a satisfying conclusion — two people reviewing their shared month, confirming it's fair, and moving on. If this
   moment feels good, everything else is worth the effort.
