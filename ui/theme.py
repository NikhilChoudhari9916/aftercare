# ruff: noqa: E501  (this file is CSS/SVG text; long lines are normal there)
"""AfterCare's look: one place for colors, type, and the page CSS (ADR-0038).

Warm and friendly: cream background, deep green for actions, coral and peach as warm accents.
Every text/background pair below must reach WCAG AA contrast (a test checks it)."""

from nicegui import ui

# Surfaces and text
BG = "#FFF8F1"  # warm cream page background
SURFACE = "#FFFFFF"
INK = "#2B2623"
INK_SOFT = "#6B5F57"
LINE = "#F0E3D6"

# Actions
PRIMARY = "#23705F"
PRIMARY_DARK = "#1B5A4C"
PRIMARY_SOFT = "#E3F2EC"

# Warm accents
CORAL = "#E4694F"  # decoration only: too light for small text
CORAL_INK = "#B3452D"  # coral that is safe for text
PEACH = "#FFEDE0"
DANGER = "#B42318"
DANGER_SOFT = "#FFE1DC"
DANGER_INK = "#7A1F12"

FONT_STACK = (
    'ui-rounded, "SF Pro Rounded", "Nunito", system-ui, -apple-system, "Segoe UI", '
    "Roboto, sans-serif"
)

# (background, text) for each kind of chip. Words always accompany the color.
CHIP_COLORS = {
    "NEW": ("#DDF1E9", "#14543F"),
    "CHANGED": ("#FFEBC2", "#7A4A00"),
    "STOPPED": ("#FFE1DC", "#9A2F1F"),
    "CONTINUED": ("#E1ECF5", "#2F4A63"),
    "AS_NEEDED": ("#ECE6FA", "#4B3F8C"),
    "CALL_911": (DANGER, "#FFFFFF"),
    "CALL_CARE_TEAM": ("#FFEBC2", "#7A4A00"),
    "NEUTRAL": (PRIMARY_SOFT, PRIMARY_DARK),
}

# Every pair that appears as text on a background, checked by tests/ui/test_theme.py.
TEXT_PAIRS = {
    "body text": (INK, BG),
    "body text on a card": (INK, SURFACE),
    "secondary text": (INK_SOFT, BG),
    "secondary text on a card": (INK_SOFT, SURFACE),
    "button text": ("#FFFFFF", PRIMARY),
    "soft button text": (PRIMARY_DARK, PRIMARY_SOFT),
    "link text": (PRIMARY, BG),
    "warm accent text": (CORAL_INK, BG),
    "alert text": (DANGER_INK, DANGER_SOFT),
    "remove button text": ("#FFFFFF", DANGER),
    "quote text": (INK, PEACH),
    **{f"{name.lower()} chip": (fg, bg) for name, (bg, fg) in CHIP_COLORS.items()},
}

CSS = f"""
:root {{
  --bg: {BG}; --surface: {SURFACE}; --ink: {INK}; --ink-soft: {INK_SOFT}; --line: {LINE};
  --primary: {PRIMARY}; --primary-dark: {PRIMARY_DARK}; --primary-soft: {PRIMARY_SOFT};
  --coral: {CORAL}; --coral-ink: {CORAL_INK}; --peach: {PEACH};
  --danger: {DANGER}; --danger-soft: {DANGER_SOFT}; --danger-ink: {DANGER_INK};
  --shadow: 0 8px 28px rgba(150, 95, 45, 0.10);
  --shadow-lift: 0 12px 34px rgba(150, 95, 45, 0.16);
}}
html, body {{
  background: var(--bg); color: var(--ink); color-scheme: light;
  font-family: {FONT_STACK}; font-size: 17px; line-height: 1.55;
}}
/* Soft warm glows behind the page, so it never feels like a blank sheet. */
body::before {{
  content: ""; position: fixed; inset: 0; z-index: -1; pointer-events: none;
  background:
    radial-gradient(520px 380px at 100% 0%, rgba(255, 208, 170, 0.45), transparent 70%),
    radial-gradient(480px 360px at 0% 100%, rgba(178, 226, 208, 0.45), transparent 70%);
}}
h1, h2, h3, p {{ margin: 0; }}
.ac-title {{ font-size: 2rem; line-height: 1.15; font-weight: 800; letter-spacing: -0.01em; }}
.ac-h2 {{ font-size: 1.35rem; font-weight: 800; }}
.ac-lead {{ font-size: 1.1rem; color: var(--ink-soft); }}
.ac-small {{ font-size: 0.9rem; color: var(--ink-soft); }}
.ac-soft {{ color: var(--ink-soft); }}

/* Layout */
.q-header.ac-header {{
  background: rgba(255, 248, 241, 0.88); backdrop-filter: blur(10px);
  color: var(--ink); border-bottom: 1px solid var(--line);
}}
.ac-header-inner {{
  width: 100%; max-width: 640px; margin: 0 auto; padding: 10px 16px;
  display: flex; align-items: center; justify-content: space-between;
}}
.ac-logo {{ display: flex; align-items: center; gap: 10px; text-decoration: none; color: var(--ink); }}
.ac-logo-badge {{
  width: 38px; height: 38px; border-radius: 14px; background: var(--primary); color: #fff;
  display: grid; place-items: center; box-shadow: 0 4px 12px rgba(35, 112, 95, 0.35);
}}
.ac-logo-text {{ font-size: 1.25rem; font-weight: 800; letter-spacing: -0.01em; }}
.ac-container {{
  width: 100%; max-width: 640px; margin: 0 auto; padding: 24px 16px 40px;
  display: flex; flex-direction: column; gap: 20px; align-items: stretch;
}}
.ac-container.has-bar {{ padding-bottom: 150px; }}

/* Cards */
.ac-card {{
  background: var(--surface); border: 1px solid var(--line); border-radius: 24px;
  box-shadow: var(--shadow); padding: 20px; gap: 12px; width: 100%;
  transition: box-shadow 0.2s ease, transform 0.2s ease, opacity 0.2s ease;
}}
/* A removed item fades, but its own buttons stay fully readable so it can be undone. */
.ac-card.is-removed {{ background: #FBF4EE; }}
.ac-card.is-removed > :not(.ac-choice-row) {{ opacity: 0.5; }}
.ac-hero {{ align-items: center; text-align: center; padding: 28px 20px; gap: 14px; }}
a.ac-action {{ text-decoration: none; color: inherit; display: block; width: 100%; }}
a.ac-action .ac-card {{ flex-direction: row; align-items: center; gap: 16px; }}
a.ac-action:hover .ac-card, a.ac-action:focus-visible .ac-card {{
  box-shadow: var(--shadow-lift); transform: translateY(-2px);
}}
.ac-icon-bubble {{
  width: 52px; height: 52px; border-radius: 18px; display: grid; place-items: center;
  background: var(--primary-soft); color: var(--primary); flex: none;
}}
.ac-icon-bubble.warm {{ background: var(--peach); color: var(--coral-ink); }}

/* Buttons: set only by class, so they look the same everywhere */
.q-btn.ac-btn {{
  border-radius: 999px; min-height: 52px; padding: 0 26px; font-size: 1.05rem;
  font-weight: 700; text-transform: none; width: 100%;
  transition: transform 0.12s ease, box-shadow 0.2s ease, background 0.2s ease;
}}
.q-btn.ac-btn:hover {{ transform: translateY(-1px); }}
.q-btn.ac-btn:active {{ transform: scale(0.98); }}
.q-btn.ac-btn-primary {{
  background: var(--primary); color: #fff; box-shadow: 0 8px 20px rgba(35, 112, 95, 0.30);
}}
.q-btn.ac-btn-primary:hover {{ background: var(--primary-dark); }}
.q-btn.ac-btn-soft {{ background: var(--primary-soft); color: var(--primary-dark); }}
.q-btn.ac-btn-ghost {{ background: transparent; color: var(--ink); border: 2px solid var(--line); }}
.q-btn.ac-btn.disabled, .q-btn.ac-btn[disabled] {{ opacity: 0.45; box-shadow: none; }}
/* Real <button> elements inside plain forms (sign out, test sign-in) */
.ac-nbtn {{
  width: 100%; min-height: 52px; border-radius: 999px; font: inherit; font-weight: 700;
  font-size: 1.05rem; cursor: pointer; background: transparent; color: var(--ink);
  border: 2px solid var(--line); transition: background 0.2s ease, transform 0.12s ease;
}}
.ac-nbtn:hover {{ background: var(--primary-soft); }}
.ac-nbtn:active {{ transform: scale(0.98); }}
.ac-nbtn.dashed {{ border-style: dashed; border-color: #D8C3AE; }}
:focus-visible {{ outline: 3px solid var(--coral); outline-offset: 2px; }}

/* Chips, notes and quotes */
.ac-chip {{
  display: inline-flex; align-items: center; gap: 4px; padding: 3px 12px;
  border-radius: 999px; font-weight: 700; font-size: 0.85rem; line-height: 1.5; width: fit-content;
}}
.ac-alert {{
  background: var(--danger-soft); color: var(--danger-ink); border-radius: 16px;
  padding: 12px 14px; font-weight: 600; width: 100%;
}}
.ac-tip {{
  background: var(--primary-soft); color: var(--primary-dark); border-radius: 16px;
  padding: 12px 14px; width: 100%;
}}
.ac-quote {{
  background: var(--peach); border-left: 4px solid var(--coral); border-radius: 12px;
  padding: 10px 14px; font-style: italic; width: 100%;
}}
.ac-quote-label {{ font-size: 0.85rem; font-weight: 700; color: var(--coral-ink); }}

/* Yes / No choice on each item */
.ac-choice-row {{ gap: 10px; flex-wrap: nowrap; width: 100%; }}
.q-btn.ac-choice {{
  flex: 1; min-height: 48px; border-radius: 999px; font-weight: 700; text-transform: none;
  background: #fff; color: var(--ink); border: 2px solid var(--line);
  transition: background 0.15s ease, color 0.15s ease, transform 0.12s ease;
}}
.q-btn.ac-choice {{ flex: 1 1 0; min-width: 0; padding: 0 8px; font-size: 0.92rem; }}
.q-btn.ac-choice .q-icon {{ font-size: 1.2rem; }}
.q-btn.ac-choice .q-btn__content {{ flex-wrap: nowrap; white-space: nowrap; }}
.q-btn.ac-choice:active {{ transform: scale(0.97); }}
.q-btn.ac-choice.is-keep {{ background: var(--primary); color: #fff; border-color: var(--primary); }}
.q-btn.ac-choice.is-remove {{ background: var(--danger); color: #fff; border-color: var(--danger); }}
.q-expansion-item.ac-fix {{ border-radius: 16px; border: 1px solid var(--line); }}

/* Upload box */
.q-uploader.ac-drop {{
  width: 100%; max-height: none; border-radius: 24px; box-shadow: none;
  border: 2px dashed #9CCBBA; background: var(--primary-soft); color: var(--primary-dark);
}}
.ac-drop .q-uploader__header {{ background: transparent; color: var(--primary-dark); padding: 26px 20px; }}
.ac-drop .q-uploader__title {{ font-size: 1.15rem; font-weight: 800; }}
.ac-drop .q-uploader__subtitle {{ display: none; }}
.ac-drop .q-uploader__list {{ min-height: 0; padding: 0; }}

/* Progress steps */
.ac-step {{ display: flex; align-items: center; gap: 14px; }}
.ac-step-dot {{
  width: 38px; height: 38px; border-radius: 50%; display: grid; place-items: center; flex: none;
  border: 2px solid var(--line); color: var(--ink-soft); background: #fff;
}}
.ac-step.is-done .ac-step-dot {{ background: var(--primary); border-color: var(--primary); color: #fff; }}
.ac-step.is-active .ac-step-dot {{
  background: var(--peach); border-color: var(--coral); color: var(--coral-ink);
  animation: ac-pulse 1.6s ease-in-out infinite;
}}
.ac-step.is-active .ac-step-text {{ font-weight: 800; }}
.ac-step.is-pending .ac-step-text {{ color: var(--ink-soft); }}

/* Sticky action bar on the confirm page */
.q-footer.ac-bar {{
  background: rgba(255, 255, 255, 0.94); backdrop-filter: blur(10px); color: var(--ink);
  border-top: 1px solid var(--line); box-shadow: 0 -8px 24px rgba(150, 95, 45, 0.10);
}}
.ac-bar-inner {{
  width: 100%; max-width: 640px; margin: 0 auto; padding: 12px 16px; gap: 14px;
  display: flex; align-items: center;
}}
.ac-bar .q-circular-progress {{ flex: none; }}
.ac-bar-count {{ white-space: nowrap; font-weight: 700; font-size: 0.95rem; }}
.ac-bar .q-btn.ac-btn {{ min-width: 0; padding: 0 14px; }}
.ac-bar .q-btn__content {{ flex-wrap: nowrap; white-space: nowrap; }}

/* Success mark that draws itself */
.ac-check-circle {{ stroke-dasharray: 190; stroke-dashoffset: 190; animation: ac-draw 0.7s ease forwards; }}
.ac-check-tick {{ stroke-dasharray: 60; stroke-dashoffset: 60; animation: ac-draw 0.45s ease 0.55s forwards; }}

/* Motion */
.fade-up {{ animation: ac-fade-up 0.5s ease both; }}
.ac-spin {{ animation: ac-spin 1s linear infinite; }}
@keyframes ac-fade-up {{ from {{ opacity: 0; transform: translateY(14px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes ac-draw {{ to {{ stroke-dashoffset: 0; }} }}
@keyframes ac-spin {{ to {{ transform: rotate(360deg); }} }}
@keyframes ac-pulse {{
  0%, 100% {{ box-shadow: 0 0 0 0 rgba(228, 105, 79, 0.35); }}
  50% {{ box-shadow: 0 0 0 9px rgba(228, 105, 79, 0); }}
}}
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ animation: none !important; transition: none !important; }}
  .ac-check-circle, .ac-check-tick {{ stroke-dashoffset: 0; }}
}}
@media (min-width: 640px) {{ .ac-title {{ font-size: 2.4rem; }} }}
"""


def apply_theme() -> None:
    """Call once at the top of every page."""
    ui.colors(
        primary=PRIMARY,
        secondary=CORAL_INK,
        accent=CORAL,
        positive=PRIMARY,
        negative=DANGER,
        warning="#B26A00",
        info=PRIMARY,
    )
    ui.dark_mode(False)
    ui.add_css(CSS)
