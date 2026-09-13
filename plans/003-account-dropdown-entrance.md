# 003 — Give the account dropdown a trigger-anchored entrance

- **Status**: DONE (applied at commit 2d7f1e4; build+lint+43 tests green)
- **Commit**: 2d7f1e4
- **Severity**: MEDIUM
- **Category**: Physicality & origin / missed opportunity
- **Estimated scope**: 1 file (`frontend/src/styles/app.css`), ~10 lines

## Problem

The account menu (Settings / Sign out) is a popover anchored to the account
button in the header. It is conditionally rendered and appears **instantly** —
no entrance, and no `transform-origin`, so it teleports into existence with no
spatial connection to the trigger that opened it.

```tsx
/* frontend/src/components/Header.tsx — the menu mounts with no animation */
{menuOpen && (
  <div className="account-menu" role="menu"> ... </div>
)}
```

```css
/* frontend/src/styles/app.css:278-282 — current, no transition/origin */
.account-menu {
  position: absolute; right: 0; top: calc(100% + 6px); z-index: 30; min-width: 180px;
  background: var(--surface-2); border: 1px solid var(--border);
  border-radius: var(--radius-sm); box-shadow: var(--shadow-halo); padding: 6px;
}
```

## Target

Scale + fade the menu in from its trigger corner (top-right, since the menu is
right-aligned under the button). Use `@starting-style` so it works with plain
conditional rendering (no JS/mount-flag needed). Popover durations are 150–200ms;
use 150ms. Never scale from 0 — start at `scale(0.97)`.

```css
/* target — frontend/src/styles/app.css, replacing the .account-menu rule */
.account-menu {
  position: absolute; right: 0; top: calc(100% + 6px); z-index: 30; min-width: 180px;
  background: var(--surface-2); border: 1px solid var(--border);
  border-radius: var(--radius-sm); box-shadow: var(--shadow-halo); padding: 6px;
  transform-origin: top right;
  opacity: 1; transform: scale(1);
  transition: opacity 150ms var(--ease-out), transform 150ms var(--ease-out);
}
@starting-style {
  .account-menu { opacity: 0; transform: scale(0.97); }
}
```

Notes:
- `transform-origin: top right` makes it grow out of the button corner, not the
  center — this is the whole point of the finding.
- `scale(0.97)` (not `scale(0)`) — the menu never appears from nothing.
- Because React unmounts the menu immediately on close, there is no exit
  animation; that is acceptable — the entrance is the win. Do **not** add a
  mount/unmount library or JS timers to force an exit.
- Under reduced motion, the global rule (see plan 001, or the current blanket
  reset) collapses the transition to instant automatically — no extra guard.

## Repo conventions to follow

- `@starting-style` is already the established entrance pattern in this codebase
  (see `frontend/src/styles/landing.css` reveal notes and the reduced-motion-safe
  approach; the tokens `--ease-out` at `tokens.css` is the standard UI curve).
- The `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)` token already exists in
  `frontend/src/styles/tokens.css` — reference it, do not hardcode the curve.

## Steps

1. In `frontend/src/styles/app.css`, extend the existing `.account-menu` rule
   (lines 278–282) by adding the three lines: `transform-origin: top right;`,
   `opacity: 1; transform: scale(1);`, and the `transition: ...` shown in the
   target. Keep all existing properties.
2. Immediately after the `.account-menu` rule, add the `@starting-style { ... }`
   block exactly as shown.

## Boundaries

- Do NOT modify `Header.tsx` or any TSX — this is CSS-only (`@starting-style`
  handles conditional-render entry without markup changes).
- Do NOT touch `.account-item` / `.account-btn` rules.
- Do NOT add a transition on `width`/`height`/`top`/`right` — only `opacity`
  and `transform`.
- If the `.account-menu` block does not match the excerpt (drift since
  `2d7f1e4`), STOP and report.

## Verification

- **Mechanical**: from `frontend/`, `npm run build` → exit 0.
- **Feel check**: run `npm run dev`, sign in (or use any signed-in state so the
  account button renders), then click the account button:
  - The menu should **grow from the top-right corner** (its trigger), scaling up
    from ~97% while fading in over ~150ms — not appear centered or full-size.
  - In DevTools → Animations, set speed to 10% and confirm the origin is the
    top-right corner, not the middle.
  - Toggle `prefers-reduced-motion: reduce` (Rendering panel) and confirm the
    menu appears instantly with no scale.
- **Done when**: the dropdown visibly scales in from the button corner at full
  speed, and appears instantly under reduced motion.
