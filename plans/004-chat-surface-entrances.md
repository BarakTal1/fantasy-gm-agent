# 004 — Add interruptible entrances to chat bubbles and tool chips

- **Status**: DONE (applied at commit 2d7f1e4; build+lint+43 tests green)
- **Commit**: 2d7f1e4
- **Severity**: LOW (missed opportunity, additive)
- **Category**: Cohesion / missed opportunity
- **Estimated scope**: 1 file (`frontend/src/styles/app.css`), ~12 lines

## Problem

In the chat view, new content teleports in:

- **Message bubbles** (`.bubble.user`, `.bubble.assistant`) appear instantly when
  a message is added — the conversation pops rather than flows.
- **Tool chips** (`.chip`) appear instantly as each tool starts during the
  assistant's "thinking" phase.

Both are rapidly/dynamically added, so this MUST use CSS **transitions +
`@starting-style`** (interruptible, retargetable), never `@keyframes` (which
restart from zero and fight streaming updates).

Current — no entrance:

```css
/* frontend/src/styles/app.css:20-22 */
.bubble { max-width: 88%; padding: 12px 14px; border-radius: var(--radius); box-shadow: var(--shadow); }
.bubble.user { ... }
.bubble.assistant { ... }
/* frontend/src/styles/app.css:24 + 220 */
.chip { ... }
```

Relevant markup (do not change it):

```tsx
/* frontend/src/components/MessageBubble.tsx — bubbles render per message */
/* frontend/src/components/ToolChips.tsx — chips render per tool, appended as tools run */
```

## Target

A subtle rise+fade for bubbles, and a small scale+fade for chips. Values from the
duration budget (dropdown/small-popover range) and physicality rules
(`scale(0.9–0.97)`, never `scale(0)`).

```css
/* target — add to frontend/src/styles/app.css */

/* Chat bubbles: rise + fade on first mount (streaming growth is unaffected —
   @starting-style only applies on entry). */
.bubble {
  transition: opacity 250ms var(--ease-out), transform 250ms var(--ease-out);
}
@starting-style {
  .bubble { opacity: 0; transform: translateY(6px); }
}

/* Tool chips: scale + fade in. They arrive one-by-one as tools start, so they
   stagger naturally in real time — no artificial delay needed. */
.chip {
  transition: opacity 200ms var(--ease-out), transform 200ms var(--ease-out);
}
@starting-style {
  .chip { opacity: 0; transform: scale(0.9); }
}
```

Why this is safe with streaming:
- `@starting-style` fires only when the element **enters** the DOM. The assistant
  bubble mounts once, animates once; subsequent token updates mutate its text
  content, which does not re-trigger the entrance.
- Transitions retarget mid-flight, so a burst of new bubbles/chips never janks.

## Repo conventions to follow

- `--ease-out` token from `frontend/src/styles/tokens.css` is the standard UI
  entrance curve — use it, do not hardcode a cubic-bezier.
- `@starting-style` + transition (not keyframes) is the interruptible-entrance
  pattern; the existing keyframe entrances (`app-rise`) are reserved for
  mount-once dashboard/landing content, which is not rapidly re-triggered.
- Add these rules near the existing `.bubble` / `.chip` polish blocks in
  `app.css` (the "Lightning polish" section around lines 214–225) for locality,
  or in a clearly labeled new block at the end — either is fine.

## Steps

1. In `frontend/src/styles/app.css`, add the `.bubble { transition: ... }` rule
   and its `@starting-style` block from the target.
2. Add the `.chip { transition: ... }` rule and its `@starting-style` block.
3. Do not modify `MessageBubble.tsx` or `ToolChips.tsx`.

## Boundaries

- Do NOT convert these to `@keyframes` — interruptibility is the whole point.
- Do NOT add `transform`/`opacity` transitions to `.md`, `.caret`, or the
  streaming text container — only the bubble wrapper and chips.
- Do NOT add per-chip `nth-child` animation-delay (they already arrive
  sequentially; artificial delay would lag behind real tool events).
- Do NOT touch any other file. No new dependencies.
- If `.bubble` (app.css:20) or `.chip` (app.css:24/220) differ from the excerpts
  (drift since `2d7f1e4`), STOP and report.

## Verification

- **Mechanical**: from `frontend/`, `npm run build` → exit 0.
- **Feel check**: run `npm run dev` with the backend, send a chat message:
  - The user bubble should rise ~6px + fade in as it appears; the assistant
    bubble the same when it starts.
  - As tools run, each chip should scale up from ~90% + fade in, one at a time.
  - Send several messages quickly and confirm **no jank / no restart-from-zero**
    flicker on bubbles already on screen (they must stay put).
  - In DevTools → Animations at 10%, confirm the bubble rises (not drops) and the
    chip scales up (never from 0).
  - Toggle `prefers-reduced-motion: reduce` and confirm bubbles/chips appear
    instantly (transition collapses) with no movement.
- **Done when**: new bubbles and chips ease in smoothly, streaming updates never
  retrigger or jank the entrance, and reduced motion shows instant appearance.
