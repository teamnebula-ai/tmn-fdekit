---
name: tmn-ui-design
description: (tmn) Build or review user interfaces that look deliberate rather than AI-generated - commit to a brief and a direction before writing code, hold an accessibility and states floor, avoid the known AI design tells, then check the result in the browser at real sizes and run the UI linter. Use for any frontend work - pages, components, dashboards, forms, landing pages, restyling, "make it look better", design reviews - and before calling UI work done.
---

# Design

Models drift toward the same few looks: cream backgrounds with a serif and a
terracotta accent, dark screens with one neon accent, identical rounded cards
with soft shadows, a tracked all-caps label above every heading. Users now
read those as "an AI made this". The fix is to decide on purpose, then check.

> Checkpoints follow the run mode in `tmn-staff-bar`: standard stops and asks before each push, post, message or hand-off to the next skill; yolo runs through. The hard lines hold in both.

**The brief wins.** If the user, the brand file or the existing design system
says otherwise, follow it. Everything below is a default, not a law.

## 1. Read the surface, then commit

Decide what kind of surface it is. That sets everything else:

| Mode | Examples | What matters most |
|---|---|---|
| **Operate** (the default) | dashboards, admin, forms, tools | scanability, density, consistency, keyboard use |
| **Read** | docs, reports, articles | measure, type, hierarchy |
| **Persuade** | landing and marketing pages | one clear message, one memorable move, one action |

Before writing code, write a short plan:

- Purpose in one sentence, and the main task a user does here.
- Palette: a neutral base, one accent, semantic colours (error, success,
  warning) that mean something. Four to six hex values.
- Type: one UI typeface (a second only on marketing pages), at most four sizes.
- A rough wireframe of the layout (ASCII is fine).
- The one thing that should be memorable. Spend boldness once.

Reread the plan against the brief and replace anything generic. In an
existing product, the plan is "match what's there": read its tokens and
components first, and reuse them.

## 2. The floor (ships every time, unannounced)

- **States:** every component has default, hover, focus-visible, active,
  loading, empty, error and disabled. Empty says what goes here and gives the
  action to fill it. Errors sit next to the field, say what's wrong and how to
  fix it, and don't apologise. Loading reserves space so nothing jumps.
- **Accessibility:** contrast at least 4.5:1 for text, 3:1 for large text and
  controls. A visible `:focus-visible` style; never `outline: none` without a
  replacement. Real `<button>` and `<a>`, never a clickable `div`. Labels above
  inputs, not placeholders. `aria-label` on icon-only buttons. Touch targets
  at least 44px.
- **Motion:** 150 to 300ms, `transform` and `opacity` only, never
  `transition: all`, and respect `prefers-reduced-motion`. Content is visible
  at rest, not waiting on an animation.
- **Responsive:** works at 375, 768, 1024 and 1440 wide with no horizontal
  page scroll. Wide tables scroll inside their own container.
- **Type and space:** body text 16px, line-height around 1.5 to 1.7, lines of
  65 to 75 characters. A 4px spacing scale. More space above a heading than
  below it. Tabular numbers in number columns.
- **Dark mode**, when there is one, is its own palette, not an inversion.

## 3. Tells to avoid

Unless the brief asks for them:

- purple, violet or cyan-on-dark gradients; gradient text; neon glows
- glassmorphism and blur as decoration
- a thick coloured border on one side of a card
- identical three-column icon + heading + text cards; cards inside cards
- the hero-metric template (huge number, tiny label, row of stats)
- a tracked all-caps eyebrow above every heading; `01 / 02 / 03` section
  numbers when order doesn't matter
- emoji or unicode glyphs as icons; an icon on every bullet; pulsing dots
- centred everything; fake screenshots built from divs
- an arrow on every link and button; middle-dot separators everywhere
- filler copy: "Welcome to", "Unlock", "Elevate", "Seamless", "Powered by AI"
- placeholder data like "John Doe", "Acme" or `99.99%`

## 4. Copy inside the UI

Name things by what the user controls ("Notifications", not "Webhook
config"). Specific verbs ("Save changes", not "Submit"). Sentence case. The
button that says "Publish" produces a "Published" message.

## 5. Check it, in bounded passes

1. Run the static check on the files you changed:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ui_lint.py" <files>`.
   Fix every error.
2. Open it in a real browser at 375 and 1440 wide. Take one screenshot each
   and look at them. Tab through the page once and check focus is visible.
   Trigger the empty and error states.
3. If the repo has them, run axe or Lighthouse accessibility
   (`npx @axe-core/cli <url>`) and fix violations.
4. Fix everything you found in one batch. Do at most one more round, then
   stop. Endless self-critique makes it worse, not better.

Report what you checked and what you saw, with the screenshots if the harness
can show them.
