# ADR-0039: A dark "midnight glass" theme, replacing the cream palette

- **Status:** Accepted
- **Date:** 2026-11-11
- **Deciders:** team
- **Supersedes:** the look in ADR-0038 (its rules on accessibility, no outside requests, and no new libraries still hold)

## Context

The warm cream design (ADR-0038) was friendly but plain. The team shared a reference they like much more: a dark, immersive hero in a rounded white-outlined panel, a floating glass navigation pill, large bold white headlines, glass badges, and white pill buttons with a dark arrow circle.

## Decision

Adopt that look, without its photograph (a photo needs a license and a privacy review, and a stock image of a clinic adds nothing for the patient).

- **Backdrop:** deep green-black with soft teal and amber glows and a faint dot grid. The hero background can later take a licensed photo through one setting; until then it is pure CSS.
- **Frame:** one large rounded panel with a white outline holds the landing hero.
- **Navigation:** a floating glass pill: logo, a few links, and the sign-in button or avatar. On a phone it collapses to the logo and one button.
- **Buttons:** white pill with a dark arrow circle on the dark backdrop; the same shape inverted (dark pill, white circle) on white surfaces.
- **Content stays readable:** medical text always sits on white rounded sheets with dark ink. Only headings, introductions and tiles use light text on the dark backdrop.
- **Product preview:** the landing page shows a glass "Today" card with clearly labelled **example** data (not real people).
- **Unchanged rules:** every text/background pair meets WCAG AA (a test checks the dark pairs too), 48 px minimum tap targets, reduced motion respected, status chips carry words, no web fonts, no CDN, no new dependencies.

## Alternatives considered

- **Keep the cream theme:** works, but the team prefers the reference.
- **Use a stock photo hero:** looks closest, but needs a license and adds an outside image request; a person's photo also implies endorsement. Left as a later option.
- **All pages dark, including medical text:** harder to read for tired eyes. Rejected for content areas.

## Consequences

- `ui/theme.py` and the components are restyled; pages keep their structure.
- The contrast test now covers the dark pairs.
- A font such as Inter, self-hosted, would match the reference better than the system font; it needs a team OK to download.
