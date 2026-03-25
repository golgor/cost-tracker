---
name: pre-commit-review
description: Runs automated linting, fixing, and basic validation on changed/staged files before commit. Returns clean summary + any remaining issues.
---

## What I do
I enforce code quality automatically:
- Run `mise run lint:docs:fix` to fix all simple issues automatically.
- Run `mise run lint:fix` to format the code and fix all simple issues automatically.
- Run `mise run lint:docs` and make sure to fix all the issues. If no obvious fix is possible, ask the user for guidance.
- Run `mise run lint` and make sure to fix all the issues. If no obvious fix is possible, ask the user for guidance.
- Run `mise run types` and make sure to fix all the issues. If no obvious fix is possible, ask the user for guidance.
- Run `mise run tests:unit` and make sure all units tests passes.
- Run `mise run test:integration` and make sure all integration tests passes.
- Only touch files that are staged or changed (via git diff)

## Rules (never break)
1. Always run the mise-commands with `fix` first to make sure to fix the obvious and simple issues first.
2. After fixes, re-run checks and report ONLY remaining violations.
3. Output a clear checklist:
   - ✅ Fixed automatically
   - ⚠️ Needs manual review
   - ❌ Blocking issues (stop commit)
4. End with: "Ready for human review? Or shall I open the files for fixes?"

## When to use me
Call me whenever someone says “review before commit”, “pre-commit check”, or “lint everything”.

## Example usage inside an agent
skill({ name: "pre-commit-review" })
# or with parameters if you extend it later: skill({ name: "pre-commit-review", files: "staged" })
