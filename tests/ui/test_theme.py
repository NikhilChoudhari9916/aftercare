import re
from pathlib import Path

import pytest

from ui.content import STATUS_WORDS, TIER_WORDS
from ui.theme import CHIP_COLORS, CSS, FONT_STACK, FONT_URL, TEXT_PAIRS

AA = 4.5  # WCAG AA for normal-size text


def _luminance(color: str) -> float:
    red, green, blue = (int(color.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4))

    def channel(value: float) -> float:
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)


def contrast(foreground: str, background: str) -> float:
    lighter, darker = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize(("name", "pair"), TEXT_PAIRS.items())
def test_every_text_and_background_pair_is_readable(name, pair):
    foreground, background = pair
    assert contrast(foreground, background) >= AA, name


def test_every_status_and_urgency_has_a_chip_color():
    assert set(STATUS_WORDS) | set(TIER_WORDS) <= set(CHIP_COLORS)


def test_the_page_never_goes_dark_and_asks_for_calm_motion_only():
    assert "color-scheme: light" in CSS
    assert "prefers-reduced-motion: reduce" in CSS


def _min_height_px(selector: str) -> int:
    rule = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert rule, selector
    return int(re.search(r"min-height:\s*(\d+)px", rule.group(1)).group(1))


@pytest.mark.parametrize(
    "selector",
    [
        ".ac-nbtn",
        ".q-btn.ac-btn",
        ".q-btn.ac-choice",
        ".ac-plan-toggle .q-btn",
        ".q-btn.ac-plan-small",
    ],
)
def test_buttons_are_big_enough_to_tap(selector):
    assert _min_height_px(selector) >= 48


FONT_FILE = Path(__file__).resolve().parents[2] / "ui" / "static" / "fonts" / "InterVariable.woff2"
FONT_LICENSE = FONT_FILE.with_name("Inter-LICENSE.txt")


def test_the_font_is_served_from_our_own_server_and_exists():
    assert FONT_URL.startswith("/static/")  # same origin: no third party sees who opened the app
    assert FONT_FILE.read_bytes()[:4] == b"wOF2"
    assert f'url("{FONT_URL}")' in CSS


def test_the_font_ships_with_its_license():
    text = FONT_LICENSE.read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE" in text.upper()
    assert "Inter Project Authors" in text


def test_the_theme_loads_nothing_from_outside():
    outside = re.findall(r"""(?:url\(|@import)\s*["']?(?:https?:)?//""", CSS)
    assert outside == []
    assert "fonts.googleapis" not in CSS and "fonts.gstatic" not in CSS


def test_the_font_stack_starts_with_inter_and_falls_back_to_the_device_font():
    assert FONT_STACK.startswith('"Inter"')
    assert "system-ui" in FONT_STACK
