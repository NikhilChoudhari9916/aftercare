import re

import pytest

from ui.content import STATUS_WORDS, TIER_WORDS
from ui.theme import CHIP_COLORS, CSS, TEXT_PAIRS

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


@pytest.mark.parametrize("selector", [".ac-nbtn", ".q-btn.ac-btn", ".q-btn.ac-choice"])
def test_buttons_are_big_enough_to_tap(selector):
    assert _min_height_px(selector) >= 48
