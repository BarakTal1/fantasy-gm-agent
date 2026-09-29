# 001 — Scope the reduced-motion reset (keep loading + comprehension motion)

- **Status**: DONE (applied at commit 2d7f1e4; build+lint+43 tests green)
- **Commit**: 2d7f1e4
- **Severity**: MEDIUM
- **Category**: Accessibility
- **Estimated scope**: 1 file (`frontend/src/styles/tokens.css`), ~15 lines

## Problem

The global reduced-motion rule is a blanket kill switch. It disables **all**
animation and transition, including motion that aids comprehension — the loading
spinner stops spinning, the "assistant is thinking" dots freeze, and the skeleton
shimmer stops. A reduced-motion user then sees a static spinner during a network
wait with no signal that anything is loading.

Per the animation philosophy, reduced motion means *fewer and gentler*
animations, **not zero** — keep opacity/color feedback that communicates state,
remove position/movement.

```css
/* frontend/src/styles/tokens.css:54 — current */
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
}
```

Affected loading indicators (all currently frozen under reduced motion):

```css
/* frontend/src/styles/app.css:26 */
.spin { animation: spin 1s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }
/* frontend/src/styles/app.css:34-36 */
.typing span { ... animation: pulse 1.2s infinite; }
@keyframes pulse { 0%,60%,100%{opacity:.3} 30%{opacity:1} }
/* frontend/src/styles/app.css:58-63 */
.skeleton { ... animation: skeleton-shimmer 1.4s ease infinite; }
```

## Target

Replace the blanket reset with a scoped one that near-zeroes durations (kills
entrances, scroll reveals, decorative loops, and movement) but **re-enables a
gentle opacity pulse for the three loading affordances** so "loading" stays
legible. The spinner's *rotation* (movement) is swapped for an opacity pulse.

Edit **only** `frontend/src/styles/tokens.css`. Replace the current block
(lines 54–56, i.e. the `@media (prefers-reduced-motion: reduce)` block) with:

```css
/* target — frontend/src/styles/tokens.css */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
  /* Keep loading legible: swap movement for a gentle opacity pulse. */
  .spin,
  .typing span,
  .skeleton {
    animation: rm-pulse 1.2s ease-in-out infinite !important;
  }
}
@keyframes rm-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
```

Rationale for the values:
- `animation-duration: 0.01ms` + `animation-iteration-count: 1` collapse every
  entrance/loop to a single instant frame (standard robust reduced-motion idiom).
- `transition-duration: 0.01ms` makes press feedback (the `scale(0.97)` on
  `:active`) and hovers resolve instantly rather than tween — the state still
  changes, just without motion.
- The `.spin / .typing span / .skeleton` override wins via `!important` and its
  own `1.2s` duration, restoring only opacity-based loading feedback.

## Repo conventions to follow

- All motion tokens and the reduced-motion block already live in
  `frontend/src/styles/tokens.css` — keep this change in that file.
- Keyframes are defined at file scope elsewhere (e.g. `@keyframes spin` in
  `app.css:26`, `@keyframes app-rise` in `app.css:454`). Define `rm-pulse` at
  file scope in `tokens.css`, after the media block, exactly as shown.
- The codebase uses `color-mix`, CSS custom properties, and `!important` only
  where genuinely needed (this reduced-motion block is the one legitimate place).

## Steps

1. In `frontend/src/styles/tokens.css`, replace the entire
   `@media (prefers-reduced-motion: reduce) { * { animation: none !important;
   transition: none !important; } }` block with the **target** block above
   (the scoped media query).
2. Immediately after that media block, add the `@keyframes rm-pulse { ... }`
   definition exactly as shown.
3. Do not touch `app.css` — the `.spin`, `.typing`, `.skeleton` selectors are
   referenced from `tokens.css` by class name only.

## Boundaries

- Do NOT touch `app.css`, `landing.css`, or any component/TSX file.
- Do NOT rename or remove the existing `spin`, `pulse`, `skeleton-shimmer`, or
  `app-rise` keyframes — they must keep working when reduced motion is OFF.
- Do NOT add dependencies.
- If the current `tokens.css` reduced-motion block does not match the excerpt
  above (drift since commit `2d7f1e4`), STOP and report.

## Verification

- **Mechanical**: from `frontend/`, run `npm run build` — expect exit 0. Run
  `npm run lint` — expect no *new* errors (pre-existing warnings are fine).
- **Feel check**: run `npm run dev`, open the app. In Chrome DevTools →
  Rendering → "Emulate CSS prefers-reduced-motion: reduce", then:
  - Trigger a chat response (or view any dashboard tab while it loads) and
    confirm the **spinner/typing dots/skeleton still pulse** (fade in/out) —
    they must not be frozen.
  - Confirm dashboard cards and landing sections appear **instantly** (no slide),
    and page scroll-reveals do not animate.
  - Press a button and confirm the `:active` state still registers (instantly).
  - Turn the emulation OFF and confirm the full spinner rotation + entrance
    staggers return unchanged.
- **Done when**: with reduced motion ON, no element slides/moves, but the three
  loading indicators still visibly pulse; with it OFF, all original motion works.
