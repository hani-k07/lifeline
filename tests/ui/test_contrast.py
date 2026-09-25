"""WCAG AA: 4.5:1 for text, 3:1 for input borders / UI boundaries - in both themes, for every pair the theme uses."""
import itertools

import pytest

from lifeline.constants import BLOOD_GROUPS
from lifeline.ui import tokens as t

THEMES = ["dark", "light"]


def ratio(fg, bg):
    return t.contrast_ratio(fg, bg)


def test_contrast_helper_matches_wcag_reference_values():
    assert t.contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert t.contrast_ratio("#777777", "#FFFFFF") == pytest.approx(4.48, abs=0.02)      # the classic "just fails AA" grey
    assert t.contrast_ratio("#FF2D4F", "#FF2D4F") == pytest.approx(1.0)


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("text", ["text_primary", "text_secondary", "text_muted"])
@pytest.mark.parametrize("surface", ["bg_base", "bg_surface", "bg_elevated", "bg_hover"])
def test_body_text_on_every_surface(theme, text, surface):
    p = t.palette(theme)
    assert ratio(getattr(p, text), getattr(p, surface)) >= 4.5, (theme, text, surface)


@pytest.mark.parametrize("theme", THEMES)
def test_buttons_and_brand_text(theme):
    p = t.palette(theme)
    assert ratio(p.on_button, p.button) >= 4.5 and ratio(p.on_button, p.button_hover) >= 4.5
    for surface in (p.bg_base, p.bg_surface):
        assert ratio(p.brand_text, surface) >= 4.5, theme                   # red text is only allowed in its AA-safe variant


@pytest.mark.parametrize("theme", THEMES)
def test_input_borders_and_focus_are_visible(theme):
    p = t.palette(theme)
    assert ratio(p.border_strong, p.bg_surface) >= 3.0 and ratio(p.border_strong, p.bg_base) >= 3.0
    assert ratio(p.button, p.bg_base) >= 3.0                               # focus ring / primary control edge


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("kind", t.KINDS)
def test_semantic_status_colours(theme, kind):
    fg, bg, border = t.kind_style(kind, theme)
    assert ratio(fg, bg) >= 4.5, (theme, kind)
    assert ratio(border, t.palette(theme).bg_surface) >= 3.0, (theme, kind)


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("group", BLOOD_GROUPS)
def test_blood_group_badges(theme, group):
    fg, bg, border, filled = t.blood_style(group, theme)
    assert ratio(fg, bg) >= 4.5, (theme, group)
    assert filled == group.endswith("+")                                    # Rh cue that does not rely on colour


@pytest.mark.parametrize("theme", THEMES)
def test_badges_are_distinguishable_without_colour(theme):
    """All eight badges carry a different printed label, and +/- differ in fill: a colour-blind user loses nothing."""
    styles = {g: t.blood_style(g, theme) for g in BLOOD_GROUPS}
    assert len(set(BLOOD_GROUPS)) == 8
    for pos, neg in itertools.pairwise(["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]):
        if pos[:-1] == neg[:-1]:
            assert styles[pos][3] != styles[neg][3]


def test_abo_hues_are_the_colour_blind_safe_okabe_ito_set():
    assert set(t.ABO_HUES.values()) == {"#0072B2", "#E69F00", "#CC79A7", "#009E73"}
    assert len({h.lower() for h in t.ABO_HUES.values()}) == 4


def test_brand_constants_and_scales():
    assert t.BRAND_NAVY == "#0D0A33" and t.BRAND_RED == "#FF2D4F" and t.DARK.bg_base == t.BRAND_NAVY
    assert all(v % 4 == 0 for v in t.SPACE.values())                       # 4/8 px spacing scale
    assert list(t.TYPE.values()) == sorted(t.TYPE.values())


def test_ensure_contrast_reaches_target_or_gives_up_at_the_extreme():
    assert t.contrast_ratio(t.ensure_contrast("#777777", "#FFFFFF", 4.5, "#000000"), "#FFFFFF") >= 4.5
    assert t.contrast_ratio(t.ensure_contrast("#000000", "#000000", 4.5, "#FFFFFF"), "#000000") >= 4.5
    assert t.ensure_contrast("#FFFFFF", "#FFFFFF", 4.5, "#FFFFFF") == "#FFFFFF"        # unreachable target: stops, no loop
