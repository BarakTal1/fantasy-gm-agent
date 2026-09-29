# 002 — Gate the starter-prompt hover lift behind a hover-capable media query

- **Status**: DONE (applied at commit 2d7f1e4; build+lint+43 tests green)
- **Commit**: 2d7f1e4
- **Severity**: MEDIUM
- **Category**: Accessibility (touch)
- **Estimated scope**: 1 file (`frontend/src/styles/app.css`), ~4 lines

## Problem

The chat empty-state starter prompts (`.example`) lift on hover via a transform.
The transform is **not** gated behind a hover-capable media query, so on a touch
device tapping a prompt fires a synthetic `:hover`, the card lifts by 1px, and
the lift **sticks** until the next tap elsewhere — a false, lingering hover state
on a list of tap targets.

```css
/* frontend/src/styles/app.css:244 — current */
.example:hover { border-color: var(--primary); box-shadow: 0 0 14px -4px var(--glow); transform: translateY(-1px); }
```

The landing page already handles this correctly for its cards, and is the pattern
to imitate:

```css
/* frontend/src/styles/landing.css:171-173 — correct exemplar */
@media (hover: hover) and (pointer: fine) {
  .lp-card:hover { transform: translateY(-3px); border-color: ...; box-shadow: var(--shadow-halo); }
}
```

## Target

Keep the color/glow hover feedback ungated (it's not movement and reads as a
harmless focus cue), but move the **transform** into a hover-capable query so it
only applies to real mouse pointers.

```css
/* target — frontend/src/styles/app.css (replacing line 244) */
.example:hover { border-color: var(--primary); box-shadow: 0 0 14px -4px var(--glow); }
@media (hover: hover) and (pointer: fine) {
  .example:hover { transform: translateY(-1px); }
}
```

## Repo conventions to follow

- The hover-capability guard `@media (hover: hover) and (pointer: fine)` is
  already used in `frontend/src/styles/landing.css:171`. Use the identical query.
- `.example` transition is already defined (`app.css:442`) with
  `transform .08s var(--ease-out)` — do not change it; it drives this transform.

## Steps

1. In `frontend/src/styles/app.css`, edit line 244: **remove**
   `transform: translateY(-1px);` from the base `.example:hover` rule, leaving
   the `border-color` and `box-shadow`.
2. Directly below that rule, add the `@media (hover: hover) and (pointer: fine)`
   block containing `.example:hover { transform: translateY(-1px); }` exactly as
   in the target.

## Boundaries

- Do NOT touch the `.example:active { transform: scale(0.985); }` rule at
  `app.css:443` — press feedback must remain for all input types.
- Do NOT change the `.example` transition (`app.css:442`) or entrance stagger
  (`app.css:464-468`).
- Do NOT touch any other file.
- If line 244 does not match the excerpt (drift since `2d7f1e4`), STOP and report.

## Verification

- **Mechanical**: from `frontend/`, `npm run build` → exit 0.
- **Feel check**: run `npm run dev`, open `/app` (the chat empty state shows the
  four starter prompts).
  - With a mouse: hover a prompt → it lifts 1px and glows; move away → it settles.
  - In DevTools, toggle device toolbar / touch emulation (or use
    `@media (hover: none)` via Rendering emulation) and **tap** a prompt: the
    border/glow may flash but the card must **not** lift or stay lifted.
- **Done when**: the lift only occurs for fine-pointer hover; taps on touch never
  leave a stuck raised card.
