# ruff: noqa: E501  (this file is CSS/SVG text; long lines are normal there)
from nicegui import ui

# Hand-drawn inline pictures, so the pages load nothing from outside.
HERO_SVG = """
<svg viewBox="0 0 320 220" width="100%" style="max-width:340px" role="img"
     aria-label="A discharge paper with a green check, a heart and a pill">
  <circle cx="160" cy="112" r="92" fill="#E3F2EC"/>
  <circle cx="246" cy="58" r="44" fill="#FFEDE0"/>
  <circle cx="72" cy="170" r="26" fill="#FFEBC2"/>
  <g transform="rotate(-6 150 110)">
    <rect x="98" y="36" width="116" height="150" rx="16" fill="#fff" stroke="#F0E3D6" stroke-width="2"/>
    <rect x="114" y="58" width="62" height="8" rx="4" fill="#CFE6DC"/>
    <rect x="114" y="78" width="84" height="7" rx="3.5" fill="#F0E3D6"/>
    <rect x="114" y="94" width="76" height="7" rx="3.5" fill="#F0E3D6"/>
    <rect x="114" y="110" width="84" height="7" rx="3.5" fill="#F0E3D6"/>
    <circle cx="190" cy="152" r="17" fill="#23705F"/>
    <path d="M181 152l7 7 12-14" fill="none" stroke="#fff" stroke-width="4"
          stroke-linecap="round" stroke-linejoin="round"/>
  </g>
  <g transform="rotate(38 242 150)">
    <rect x="212" y="136" width="60" height="28" rx="14" fill="#fff" stroke="#E4694F" stroke-width="3"/>
    <path d="M242 136h-14a14 14 0 0 0 0 28h14z" fill="#E4694F"/>
  </g>
  <path d="M78 76c-9-9-24 0-17 12 4 6 17 14 17 14s13-8 17-14c7-12-8-21-17-12z" fill="#E4694F"/>
  <circle cx="268" cy="104" r="4" fill="#E4694F"/>
  <circle cx="52" cy="124" r="3.5" fill="#23705F"/>
</svg>
"""

CHECK_SVG = """
<svg viewBox="0 0 80 80" width="96" height="96" role="img" aria-label="Done">
  <circle class="ac-check-circle" cx="40" cy="40" r="30" fill="#E3F2EC" stroke="#23705F" stroke-width="4"/>
  <path class="ac-check-tick" d="M27 41l9 9 18-20" fill="none" stroke="#23705F" stroke-width="5"
        stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""


def hero_picture() -> ui.html:
    return ui.html(HERO_SVG, sanitize=False)


def success_check() -> ui.html:
    return ui.html(CHECK_SVG, sanitize=False)
