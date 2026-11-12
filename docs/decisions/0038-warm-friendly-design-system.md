# ADR-0038: A warm, friendly design system on NiceGUI, with no new libraries

- **Status:** Partly superseded by ADR-0039 (the look; the accessibility and privacy rules still hold)
- **Date:** 2026-11-11
- **Deciders:** team
- **Supersedes:** none (refines how ADR-0010 is styled)

## Context

The first pages used default Quasar styling and looked plain. AfterCare's users are tired patients and caregivers, often on a phone, reading about their own health. The screens should feel calm, kind, and clear, not clinical.

## Decision

Keep NiceGUI (ADR-0010) and give it a proper design system. **No new dependencies.**

- **Mood:** warm and friendly: a cream background, a deep green for actions, coral and peach as warm accents, large rounded cards, soft shadows, and gentle motion.
- **One source of truth:** `ui/theme.py` holds the colors, type, spacing, and the page CSS. Pages use shared components in `ui/components/` and do not style things one by one.
- **Accessible by rule:** every text and background pair in the palette must reach WCAG AA contrast (4.5:1). A test checks it. Tap targets are at least 48 px. Motion is switched off for people who ask for reduced motion. The light theme is forced because the palette is designed for it.
- **No outside requests:** no Google Fonts and no CDN. Pages load nothing from a third party, because a font request would tell that party a person opened a health app. Until an open-licensed font is added to our own server, the font is the device's own system font.
- **Phone first:** the layout is one column up to about 640 px, which also reads well on a laptop.
- **Status is never color alone:** every status chip also has words ("Stopped", "New").

## Alternatives considered

- **Rewrite in React with shadcn/ui and Framer Motion:** the best possible polish, but days of work plus a Node toolchain, and it would compete with the safety gate and Q&A for time. It stays possible later because the backend is a plain API.
- **HTMX with Jinja and Tailwind:** very controllable, but a full rewrite and it breaks the "UI is its own NiceGUI process" rule.
- **Flet or Reflex:** new frameworks with weaker accessibility on the web.

## Consequences

- New files: `ui/theme.py`, `ui/components/`. Pages are restyled to use them.
- A self-hosted open-licensed font (for example Nunito) can be added later in one place; it needs the team's OK to download it.
- A contrast test and a status-chip test protect the palette.
