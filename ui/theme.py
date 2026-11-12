# ruff: noqa: E501  (this file is CSS text; long lines are normal there)
"""AfterCare's look: one place for colors, type, and the page CSS (ADR-0039).

"Midnight glass": a deep green-black backdrop with soft glows, glass pills and tiles, white pill
buttons with a dark arrow, and white rounded sheets for anything a patient must read closely.
Every text/background pair below must reach WCAG AA contrast (tests/ui/test_theme.py checks it)."""

from nicegui import ui

# Dark backdrop
NIGHT = "#09120F"
NIGHT_GLOW = "#12302A"  # the lightest teal the glows add to the backdrop
WHITE = "#FFFFFF"
MUTED = "#BCCBC6"  # secondary text on the dark backdrop
MINT = "#6EE7C2"  # accent on dark: dots, icons, small highlights
AMBER = "#FFB36B"  # warm glow, decoration only

# White sheets (anything a patient must read closely)
SURFACE = "#FFFFFF"
INK = "#14201C"
INK_SOFT = "#55645F"
LINE = "#E3EBE8"

# Actions on white sheets
PRIMARY = "#0F6B58"
PRIMARY_DARK = "#0A4F41"
PRIMARY_SOFT = "#E0F2EC"

# Warm accents and warnings
CORAL = "#E4694F"  # decoration only: too light for small text
CORAL_INK = "#B3452D"  # coral that is safe for text on white
PEACH = "#FFEDE0"
DANGER = "#B42318"
DANGER_SOFT = "#FFE1DC"
DANGER_INK = "#7A1F12"

FONT_STACK = (
    '"Inter", system-ui, -apple-system, "Segoe UI Variable", "Segoe UI", Roboto, '
    '"Helvetica Neue", sans-serif'
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
    # on the dark backdrop
    "headline on the dark backdrop": (WHITE, NIGHT),
    "headline on the lightest glow": (WHITE, NIGHT_GLOW),
    "secondary text on the dark backdrop": (MUTED, NIGHT),
    "secondary text on the lightest glow": (MUTED, NIGHT_GLOW),
    "accent on the dark backdrop": (MINT, NIGHT),
    "white pill button": (NIGHT, WHITE),
    "dark pill button": (WHITE, NIGHT),
    "white on glass over the amber glow": (WHITE, "#3B3027"),
    "tip on the dark backdrop": ("#DFF7EE", "#16302A"),
    # on white sheets
    "body text on a sheet": (INK, SURFACE),
    "secondary text on a sheet": (INK_SOFT, SURFACE),
    "link or label on a sheet": (PRIMARY, SURFACE),
    "soft button on a sheet": (PRIMARY_DARK, PRIMARY_SOFT),
    "warm label on a sheet": (CORAL_INK, SURFACE),
    "warm label on a quote": (CORAL_INK, PEACH),
    "quote text": (INK, PEACH),
    "alert text": (DANGER_INK, DANGER_SOFT),
    "selected keep button": (WHITE, PRIMARY),
    "selected remove button": (WHITE, DANGER),
    **{f"{name.lower()} chip": (fg, bg) for name, (bg, fg) in CHIP_COLORS.items()},
}

ROOT = f"""
:root {{
  --bg: {NIGHT}; --glow: {NIGHT_GLOW}; --white: {WHITE}; --muted: {MUTED}; --mint: {MINT}; --amber: {AMBER};
  --surface: {SURFACE}; --ink: {INK}; --ink-soft: {INK_SOFT}; --line: {LINE};
  --primary: {PRIMARY}; --primary-dark: {PRIMARY_DARK}; --primary-soft: {PRIMARY_SOFT};
  --coral: {CORAL}; --coral-ink: {CORAL_INK}; --peach: {PEACH};
  --danger: {DANGER}; --danger-soft: {DANGER_SOFT}; --danger-ink: {DANGER_INK};
  --font: {FONT_STACK};
}}
"""

CSS = (
    ROOT
    + """
html { background: var(--bg); }
/* body stays transparent: a body background would paint over the glows behind it */
html, body {
  color: var(--white); color-scheme: light;
  font-family: var(--font); font-size: 17px; line-height: 1.55; -webkit-font-smoothing: antialiased;
}
/* Soft glows and a faint dot grid behind every page */
body::before {
  content: ""; position: fixed; inset: 0; z-index: -1; pointer-events: none;
  background:
    radial-gradient(640px 420px at 100% 0%, rgba(255, 179, 107, 0.16), transparent 70%),
    radial-gradient(720px 520px at 0% 100%, rgba(110, 231, 194, 0.16), transparent 70%),
    radial-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1.5px) 0 0 / 24px 24px,
    linear-gradient(170deg, #0D1F1A, var(--bg) 60%);
}
h1, h2, h3, p { margin: 0; }

/* Text. Dark pages use light text; a white sheet switches the variables back. */
.ac-title { font-size: clamp(2.1rem, 6.4vw, 3.5rem); line-height: 1.06; font-weight: 700; letter-spacing: -0.025em; color: var(--white); }
.ac-h2 { font-size: 1.3rem; font-weight: 700; letter-spacing: -0.01em; }
.ac-lead { font-size: 1.08rem; color: var(--muted); }
.ac-small { font-size: 0.9rem; color: var(--muted); }
.ac-soft { color: var(--muted); }
.ac-card, .ac-bar, .q-menu { --muted: var(--ink-soft); color: var(--ink); }
.ac-card .ac-title { color: var(--ink); }

/* Floating glass navigation pill */
.q-header.ac-header { background: transparent; border: 0; pointer-events: none; }
.ac-nav {
  pointer-events: auto; margin: 12px auto 0; width: min(1080px, calc(100% - 24px));
  padding: 8px 10px 8px 16px; display: flex; align-items: center; justify-content: space-between; gap: 12px;
  background: rgba(14, 30, 26, 0.62); backdrop-filter: blur(16px) saturate(140%);
  border: 1px solid rgba(255, 255, 255, 0.16); border-radius: 999px;
}
.ac-logo { display: flex; align-items: center; gap: 8px; text-decoration: none; color: var(--white); }
.ac-logo-text { font-size: 1.2rem; font-weight: 700; letter-spacing: -0.02em; }
.ac-nav-links { display: flex; gap: 4px; margin-right: auto; margin-left: 20px; }
a.ac-nav-link {
  color: var(--muted); padding: 8px 14px; border-radius: 999px; text-decoration: none;
  font-weight: 600; font-size: 0.95rem; transition: background 0.2s ease, color 0.2s ease;
}
a.ac-nav-link:hover { color: var(--white); background: rgba(255, 255, 255, 0.10); }
a.ac-nav-link.is-current { color: var(--white); }
a.ac-nav-link.is-current::before {
  content: ""; display: inline-block; width: 6px; height: 6px; border-radius: 50%;
  background: var(--mint); margin-right: 8px; vertical-align: middle;
}
.ac-avatar {
  width: 42px; height: 42px; border-radius: 50%; display: grid; place-items: center;
  background: var(--white); color: var(--bg); font-weight: 700;
}
@media (max-width: 640px) { .ac-nav-links { display: none; } }

/* Layout */
.ac-container {
  width: 100%; max-width: 680px; margin: 0 auto; padding: 28px 16px 48px;
  display: flex; flex-direction: column; gap: 20px; align-items: stretch;
}
.ac-container.wide { max-width: 1080px; padding-left: 12px; padding-right: 12px; }
.ac-container.has-bar { padding-bottom: 130px; }

/* The big rounded hero panel with a white outline */
.ac-panel {
  position: relative; overflow: hidden; width: 100%; border-radius: 32px;
  border: 4px solid rgba(255, 255, 255, 0.92); padding: 56px 40px; gap: 32px;
  display: grid; grid-template-columns: 1.1fr 0.9fr; align-items: center;
  background:
    radial-gradient(520px 380px at 88% 8%, rgba(255, 179, 107, 0.34), transparent 65%),
    radial-gradient(640px 460px at 6% 100%, rgba(110, 231, 194, 0.30), transparent 65%),
    radial-gradient(rgba(255, 255, 255, 0.07) 1px, transparent 1.5px) 0 0 / 22px 22px,
    linear-gradient(155deg, #123B34, #0A1815 62%);
  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.5);
}
.ac-panel-copy { display: flex; flex-direction: column; gap: 20px; align-items: flex-start; }
@media (max-width: 880px) {
  .ac-panel { grid-template-columns: 1fr; padding: 36px 20px 28px; border-width: 3px; border-radius: 28px; }
}

/* Glass badge, tiles and the product preview */
.ac-badge {
  display: inline-flex; align-items: center; gap: 10px; padding: 6px 16px 6px 6px; border-radius: 999px;
  background: rgba(255, 255, 255, 0.10); border: 1px solid rgba(255, 255, 255, 0.20);
  backdrop-filter: blur(10px); font-size: 0.92rem; font-weight: 500; color: var(--white);
}
.ac-avatars { display: flex; }
.ac-avatars > span {
  width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center;
  border: 2px solid #1B3A33; margin-left: -8px; color: var(--bg);
}
.ac-avatars > span:first-child { margin-left: 0; }
.ac-glass-card {
  background: rgba(255, 255, 255, 0.07); border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 24px; backdrop-filter: blur(14px); padding: 20px; gap: 10px; width: 100%;
  color: var(--white); transition: transform 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
}
.ac-preview { background: rgba(255, 255, 255, 0.10); border-color: rgba(255, 255, 255, 0.22); box-shadow: 0 24px 60px rgba(0, 0, 0, 0.4); animation: ac-float 6s ease-in-out infinite; }
.ac-preview-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 12px; border-radius: 16px; background: rgba(255, 255, 255, 0.08); width: 100%; }
.ac-preview-time { font-weight: 700; color: var(--mint); }
.ac-eyebrow { font-size: 0.78rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: var(--mint); }
a.ac-action { text-decoration: none; color: inherit; display: block; width: 100%; }
a.ac-action .ac-glass-card { flex-direction: row; align-items: center; gap: 16px; }
a.ac-action:hover .ac-glass-card, a.ac-action:focus-visible .ac-glass-card {
  transform: translateY(-3px); background: rgba(255, 255, 255, 0.11); box-shadow: 0 18px 40px rgba(0, 0, 0, 0.35);
}
a.ac-action .ac-arrow { background: var(--white); color: var(--bg); margin-left: 0; }
.ac-icon-bubble {
  width: 52px; height: 52px; border-radius: 18px; display: grid; place-items: center; flex: none;
  background: rgba(255, 255, 255, 0.12); color: var(--mint);
}
.ac-icon-bubble.warm { color: var(--amber); }
.ac-step-number { font-size: 0.85rem; font-weight: 700; color: var(--mint); letter-spacing: 0.08em; }

/* White sheets: for anything the patient must read closely */
.ac-card {
  background: var(--surface); border-radius: 24px; padding: 20px; gap: 12px; width: 100%;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35);
  transition: box-shadow 0.2s ease, transform 0.2s ease, opacity 0.2s ease;
}
/* A removed item fades, but its own buttons stay fully readable so it can be undone. */
.ac-card.is-removed { background: #EEF3F1; }
.ac-card.is-removed > :not(.ac-choice-row) { opacity: 0.5; }
.ac-hero { align-items: center; text-align: center; padding: 32px 22px; gap: 14px; }

/* Buttons: set only by class, so they look the same everywhere */
.q-btn.ac-btn {
  border-radius: 999px; min-height: 56px; padding: 0 26px; font-size: 1.02rem; font-weight: 700;
  text-transform: none; width: 100%; letter-spacing: -0.005em;
  transition: transform 0.12s ease, box-shadow 0.2s ease, background 0.2s ease;
}
.q-btn.ac-btn.has-arrow { padding: 0 8px 0 24px; }
.q-btn.ac-btn.has-arrow .q-btn__content { justify-content: space-between; flex-wrap: nowrap; white-space: nowrap; }
.q-btn.ac-btn.ac-fit { width: auto; align-self: flex-start; }
.q-btn.ac-btn.ac-compact { min-height: 44px; font-size: 0.95rem; padding: 0 6px 0 18px; }
.q-btn.ac-btn.ac-compact .ac-arrow { width: 32px; height: 32px; margin-left: 10px; }
.q-btn.ac-btn:hover { transform: translateY(-1px); }
.q-btn.ac-btn:active { transform: scale(0.98); }
.ac-arrow {
  width: 42px; height: 42px; border-radius: 50%; display: grid; place-items: center; flex: none;
  margin-left: 16px; background: var(--bg); color: var(--white); transition: transform 0.2s ease;
}
.q-btn.ac-btn:hover .ac-arrow { transform: translateX(3px); }
/* on the dark backdrop */
.q-btn.ac-btn-primary { background: var(--white); color: var(--bg); box-shadow: 0 12px 30px rgba(0, 0, 0, 0.35); }
.q-btn.ac-btn-soft { background: rgba(255, 255, 255, 0.12); color: var(--white); border: 1px solid rgba(255, 255, 255, 0.28); backdrop-filter: blur(10px); }
.q-btn.ac-btn-ghost { background: transparent; color: var(--white); border: 1.5px solid rgba(255, 255, 255, 0.35); }
/* on white sheets and the white action bar: the same shapes, inverted */
.ac-card .q-btn.ac-btn-primary, .ac-bar .q-btn.ac-btn-primary { background: var(--bg); color: var(--white); box-shadow: 0 10px 24px rgba(9, 18, 15, 0.28); }
.ac-card .q-btn.ac-btn-primary .ac-arrow, .ac-bar .q-btn.ac-btn-primary .ac-arrow { background: var(--white); color: var(--bg); }
.ac-card .q-btn.ac-btn-soft { background: var(--primary-soft); color: var(--primary-dark); border-color: transparent; }
.ac-card .q-btn.ac-btn-ghost { color: var(--ink); border-color: var(--line); }
.q-btn.ac-btn.disabled, .q-btn.ac-btn[disabled] { opacity: 0.45; box-shadow: none; }
/* Real <button> elements inside plain forms (test sign-in, sign out) */
.ac-nbtn {
  width: 100%; min-height: 48px; border-radius: 999px; font: inherit; font-weight: 600; font-size: 0.98rem;
  cursor: pointer; background: rgba(255, 255, 255, 0.08); color: var(--white);
  border: 1.5px dashed rgba(255, 255, 255, 0.4); transition: background 0.2s ease, transform 0.12s ease;
}
.ac-nbtn:hover { background: rgba(255, 255, 255, 0.16); }
.ac-nbtn:active { transform: scale(0.98); }
.q-menu .ac-nbtn { background: transparent; color: var(--ink); border: 1.5px solid var(--line); }
.q-menu .ac-nbtn:hover { background: var(--primary-soft); }
:focus-visible { outline: 3px solid var(--mint); outline-offset: 2px; }
.ac-card :focus-visible, .ac-bar :focus-visible, .q-menu :focus-visible { outline-color: var(--primary); }

/* Chips, notes and quotes */
.ac-chip { display: inline-flex; align-items: center; gap: 4px; padding: 3px 12px; border-radius: 999px; font-weight: 700; font-size: 0.85rem; line-height: 1.5; width: fit-content; }
.ac-alert { background: var(--danger-soft); color: var(--danger-ink); border-radius: 16px; padding: 12px 14px; font-weight: 600; width: 100%; }
.ac-tip { background: rgba(110, 231, 194, 0.12); color: #DFF7EE; border: 1px solid rgba(110, 231, 194, 0.30); border-radius: 16px; padding: 12px 14px; width: 100%; }
.ac-card .ac-tip { background: var(--primary-soft); color: var(--primary-dark); border-color: transparent; }
.ac-quote { background: var(--peach); color: var(--ink); border-left: 4px solid var(--coral); border-radius: 12px; padding: 10px 14px; font-style: italic; width: 100%; }
.ac-quote-label { font-size: 0.85rem; font-weight: 700; color: var(--coral-ink); }

/* "Looks right" / "Remove" on each item */
.ac-choice-row { gap: 10px; flex-wrap: nowrap; width: 100%; }
.q-btn.ac-choice {
  flex: 1 1 0; min-width: 0; padding: 0 8px; font-size: 0.92rem; min-height: 48px; border-radius: 999px;
  font-weight: 700; text-transform: none; background: #fff; color: var(--ink); border: 1.5px solid var(--line);
  transition: background 0.15s ease, color 0.15s ease, transform 0.12s ease;
}
.q-btn.ac-choice .q-icon { font-size: 1.2rem; }
.q-btn.ac-choice .q-btn__content { flex-wrap: nowrap; white-space: nowrap; }
.q-btn.ac-choice:active { transform: scale(0.97); }
.q-btn.ac-choice.is-keep { background: var(--primary); color: #fff; border-color: var(--primary); }
.q-btn.ac-choice.is-remove { background: var(--danger); color: #fff; border-color: var(--danger); }
.q-expansion-item.ac-fix { border-radius: 16px; border: 1px solid var(--line); }

/* Upload box: dark glass with a dashed edge */
.q-uploader.ac-drop {
  width: 100%; max-height: none; border-radius: 24px; box-shadow: none; backdrop-filter: blur(10px);
  border: 2px dashed rgba(255, 255, 255, 0.38); background: rgba(255, 255, 255, 0.06); color: var(--white);
}
.ac-drop .q-uploader__header { background: transparent; color: var(--white); padding: 28px 22px; }
.ac-drop .q-uploader__title { font-size: 1.15rem; font-weight: 700; }
.ac-drop .q-uploader__subtitle { display: none; }
.ac-drop .q-uploader__list { min-height: 0; padding: 0; color: var(--white); }
.ac-drop .q-uploader__file { color: var(--white); }

/* Progress steps (inside a white sheet) */
.ac-step { display: flex; align-items: center; gap: 14px; }
.ac-step-dot { width: 38px; height: 38px; border-radius: 50%; display: grid; place-items: center; flex: none; border: 2px solid var(--line); color: var(--ink-soft); background: #fff; }
.ac-step.is-done .ac-step-dot { background: var(--primary); border-color: var(--primary); color: #fff; }
.ac-step.is-active .ac-step-dot { background: var(--peach); border-color: var(--coral); color: var(--coral-ink); animation: ac-pulse 1.6s ease-in-out infinite; }
.ac-step.is-active .ac-step-text { font-weight: 700; }
.ac-step.is-pending .ac-step-text { color: var(--ink-soft); }

/* Floating white action bar on the confirm page */
.q-footer.ac-bar { background: transparent; border: 0; box-shadow: none; pointer-events: none; }
.ac-bar-inner {
  pointer-events: auto; width: min(640px, calc(100% - 24px)); margin: 0 auto 12px; padding: 8px 8px 8px 16px; gap: 12px;
  display: flex; align-items: center; background: #fff; border-radius: 999px; box-shadow: 0 18px 50px rgba(0, 0, 0, 0.45);
}
.ac-bar .q-circular-progress { flex: none; }
.ac-bar-count { white-space: nowrap; font-weight: 700; font-size: 0.95rem; }
.ac-bar .q-btn.ac-btn { min-width: 0; }

/* Success mark that draws itself */
.ac-check-circle { stroke-dasharray: 190; stroke-dashoffset: 190; animation: ac-draw 0.7s ease forwards; }
.ac-check-tick { stroke-dasharray: 60; stroke-dashoffset: 60; animation: ac-draw 0.45s ease 0.55s forwards; }

/* Motion */
.fade-up { animation: ac-fade-up 0.55s ease both; }
.ac-spin { animation: ac-spin 1s linear infinite; }
@keyframes ac-fade-up { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: none; } }
@keyframes ac-float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
@keyframes ac-draw { to { stroke-dashoffset: 0; } }
@keyframes ac-spin { to { transform: rotate(360deg); } }
@keyframes ac-pulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(228, 105, 79, 0.35); } 50% { box-shadow: 0 0 0 9px rgba(228, 105, 79, 0); } }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
  .ac-check-circle, .ac-check-tick { stroke-dashoffset: 0; }
}
"""
)


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
    ui.dark_mode(False)  # Quasar's own controls (inputs, menus) sit on white sheets
    ui.add_css(CSS)
