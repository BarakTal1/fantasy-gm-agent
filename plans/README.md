# Animation improvement plans

Audit of the Lightning frontend's motion, at commit `2d7f1e4`, using the
`improve-animations` playbook (Emil Kowalski's philosophy). The codebase came in
already strong — no `transition: all`, no `ease-in`, no `scale(0)`, all UI
durations ≤ 300ms, press feedback present, reduced-motion + hover gates present,
no Framer Motion perf traps. These plans close the remaining gaps.

Each plan is self-contained: exact file paths, current-code excerpts, target
values, and a feel-check. Any agent can execute one without further context.

| # | Plan | Severity | Category | Status |
| --- | --- | --- | --- | --- |
| 001 | [Scope the reduced-motion reset](001-scope-reduced-motion.md) | MEDIUM | Accessibility | DONE |
| 002 | [Gate the starter-prompt hover lift](002-gate-example-hover-lift.md) | MEDIUM | A11y / touch | DONE |
| 003 | [Account dropdown trigger-anchored entrance](003-account-dropdown-entrance.md) | MEDIUM | Physicality / origin | DONE |
| 004 | [Chat bubble + tool chip entrances](004-chat-surface-entrances.md) | LOW | Missed opportunity | DONE |
| 005 | [Remove dead `ease` transitions](005-remove-dead-ease-transitions.md) | LOW | Cleanup | DONE |

## Recommended execution order

1. **001** — highest leverage (correctness for reduced-motion users; loading
   indicators currently freeze). Do first.
2. **002** — quick, isolated touch-a11y fix.
3. **003** — self-contained visible polish.
4. **004** — additive delight in the chat surface.
5. **005** — trivial cleanup; do last so it doesn't collide with other edits.

## Dependencies

- All five touch `frontend/src/styles/` only; **001** edits `tokens.css`, the
  rest edit `app.css`. None conflict — they touch different rules.
- **001 and 003/004** interact conceptually (001 defines how reduced motion is
  handled globally; 003/004 rely on transitions collapsing to instant under
  reduced motion). Both behave correctly whether 001 lands before or after —
  the transition-based entrances in 003/004 degrade safely under either the old
  blanket reset or the new scoped one. No hard ordering required.

## How to execute

- All edits are CSS-only and low-risk. To apply directly, follow each plan's
  Steps and Verification.
- Or run them via an executor: `improve-animations execute plans/001-...md`
  (dispatches an isolated worktree edit + an animation-review verdict).
