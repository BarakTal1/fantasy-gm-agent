# 005 — Remove three dead `ease` transition declarations

- **Status**: DONE (applied at commit 2d7f1e4; build+lint+43 tests green)
- **Commit**: 2d7f1e4
- **Severity**: LOW
- **Category**: Cohesion / cleanup
- **Estimated scope**: 1 file (`frontend/src/styles/app.css`), 3 edits

## Problem

Three `.tab` / `.icon-btn` / `.example` rules declare a `transition` using the
weak built-in `ease` curve. Each is **fully superseded** by a later
same-specificity rule (the "Phase 8" polish block) that restates the transition
with the strong `var(--ease-out)` token. The earlier declarations have **no
runtime effect** (later same-specificity wins), but they're dead code that
invites future drift — someone editing the top declaration would see no change
and be confused.

```css
/* frontend/src/styles/app.css:204 — dead transition (superseded by :440) */
.tab { ...; transition: color .18s ease, background .18s ease, box-shadow .18s ease; }

/* frontend/src/styles/app.css:228 — dead transition (superseded by :434) */
.icon-btn { ...; transition: box-shadow .18s ease, transform .05s ease; }

/* frontend/src/styles/app.css:243 — dead transition (superseded by :442) */
.example { background: var(--surface); font-weight: 600;
  transition: border-color .18s ease, box-shadow .18s ease, transform .05s ease; }
```

The surviving winners (do NOT change these):

```css
/* app.css:440 */ .tab { transition: color .18s var(--ease-out), background .18s var(--ease-out), box-shadow .18s var(--ease-out), transform .06s var(--ease-out); }
/* app.css:434 */ .icon-btn { transition: box-shadow .18s var(--ease-out), transform .06s var(--ease-out); }
/* app.css:442 */ .example { transition: border-color .18s var(--ease-out), box-shadow .18s var(--ease-out), transform .08s var(--ease-out); }
```

## Target

Delete only the dead `transition:` declarations from the three earlier rules,
leaving every other property on those rules intact.

- `app.css:204` `.tab` — remove `transition: color .18s ease, background .18s ease, box-shadow .18s ease;`
- `app.css:228` `.icon-btn` — remove `transition: box-shadow .18s ease, transform .05s ease;`
- `app.css:243` `.example` — remove `transition: border-color .18s ease, box-shadow .18s ease, transform .05s ease;`

## Repo conventions to follow

- The canonical transitions already live in the Phase-8 block (app.css:434–450),
  all using `var(--ease-out)`. That block is the single source of truth for these
  three selectors' transitions after this change.

## Steps

1. In `frontend/src/styles/app.css` line 204, delete the `transition: ... ;`
   portion of the `.tab` rule. Keep `border-radius`, `padding`, `font-weight`,
   `color`, and `border`.
2. In line 228, delete the `transition: ... ;` portion of the `.icon-btn` rule.
   Keep `background`, `color`, and `box-shadow`.
3. In line 243, delete the `transition: ... ;` portion of the `.example` rule.
   Keep `background` and `font-weight`.

## Boundaries

- Do NOT touch lines 434, 440, or 442 (the surviving transitions).
- Do NOT remove any non-`transition` property from the three rules.
- Do NOT touch any other file.
- If any of the three lines do not match the excerpts (drift since `2d7f1e4`),
  STOP and report — do not guess which transition is dead.

## Verification

- **Mechanical**: from `frontend/`, `npm run build` → exit 0; `npm run test` →
  all pass (43 tests at time of writing).
- **Feel check**: run `npm run dev`. Confirm **no behavior change**:
  - Nav tabs still transition color/background/glow on hover/active with the
    same feel as before.
  - The send button (`.icon-btn`) still eases its box-shadow on hover and scales
    on press.
  - Starter prompts (`.example`) still ease border/glow/press exactly as before.
- **Done when**: the three dead `transition` declarations are gone, the build and
  tests pass, and there is zero visible change to tab / icon-button / example
  motion.
