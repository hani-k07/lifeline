"""Design tokens: the ONLY place colours, spacing, type and radii are defined.

Brand: deep navy #0D0A33 with the blood-drop red #FF2D4F. Red is an accent for alerts and the brand mark, not a
decoration: filled buttons use a darker red that meets WCAG AA with white text, and red *text* uses AA-safe variants.
Every text/background pair used by the theme is checked by tests/ui/test_contrast.py (AA: 4.5:1 for text, 3:1 for
input borders and other UI boundaries), in both themes.
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------- scales
SPACE = {1: 4, 2: 8, 3: 12, 4: 16, 5: 24, 6: 32, 7: 48}          # px, a 4/8 scale
RADIUS = {"sm": 6, "md": 8, "lg": 12, "pill": 999}
FONT_STACK = '"Inter", "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
MONO_STACK = '"JetBrains Mono", "IBM Plex Mono", ui-monospace, SFMono-Regular, Consolas, monospace'
TYPE = {"xs": 0.75, "sm": 0.8125, "base": 0.9375, "md": 1.0625, "lg": 1.25, "xl": 1.5, "2xl": 1.875}   # rem

BRAND_NAVY = "#0D0A33"
BRAND_RED = "#FF2D4F"


# ---------------------------------------------------------------- colour maths
def _rgb(hex_colour: str) -> tuple[int, int, int]:
    h = hex_colour.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, round(c))) for c in rgb))


def mix(a: str, b: str, t: float) -> str:
    """`t` of the way from colour a to colour b."""
    ra, rb = _rgb(a), _rgb(b)
    return _hex(tuple(x + (y - x) * t for x, y in zip(ra, rb, strict=True)))  # type: ignore[arg-type]


def luminance(hex_colour: str) -> float:
    def channel(c: int) -> float:
        v = c / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in _rgb(hex_colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str) -> float:
    hi, lo = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def ensure_contrast(fg: str, bg: str, target: float = 4.5, toward: str = "#FFFFFF") -> str:
    """Nudge `fg` toward `toward` in 4% steps until it reaches `target` contrast against `bg`."""
    colour, step = fg, 0.0
    while contrast_ratio(colour, bg) < target and step < 1.0:
        step += 0.04
        colour = mix(fg, toward, step)
    return colour


# ---------------------------------------------------------------- palettes
@dataclass(frozen=True)
class Palette:
    name: str
    bg_base: str
    bg_surface: str
    bg_elevated: str
    bg_hover: str
    border_subtle: str
    border_strong: str            # input borders / boundaries that must reach 3:1
    text_primary: str
    text_secondary: str
    text_muted: str
    brand: str                    # the drop red: accents, logo, alert edge - not body text
    brand_text: str               # red that is safe to use as text
    button: str                   # filled primary button (white text is AA on it)
    button_hover: str
    on_button: str
    success: str
    warning: str
    danger: str
    info: str
    shadow: str

    def tint(self, colour: str, amount: float = 0.14) -> str:
        return mix(self.bg_surface, colour, amount)

    def readable(self, colour: str, on: str | None = None, target: float = 4.5) -> str:
        """`colour` adjusted (toward white in dark mode, black in light mode) to be AA-readable on `on`."""
        toward = "#FFFFFF" if self.name == "dark" else "#000000"
        return ensure_contrast(colour, on or self.bg_surface, target, toward)


DARK = Palette(
    name="dark", bg_base=BRAND_NAVY, bg_surface="#16124A", bg_elevated="#1F1B5C", bg_hover="#2A2670",
    border_subtle="#2E2A78", border_strong="#7A77C4",
    text_primary="#F4F5FF", text_secondary="#C6C9EA", text_muted="#A9ADD9",
    brand=BRAND_RED, brand_text="#FF6B84", button="#D9153F", button_hover="#C11238", on_button="#FFFFFF",
    success="#34D399", warning="#FBBF24", danger="#FF6B84", info="#7DB7FF", shadow="0 1px 2px rgba(0,0,0,.45)",
)
LIGHT = Palette(
    name="light", bg_base="#F5F6FB", bg_surface="#FFFFFF", bg_elevated="#EDEFF9", bg_hover="#E2E5F5",
    border_subtle="#DADDF0", border_strong="#6B6F99",
    text_primary=BRAND_NAVY, text_secondary="#3B3E6B", text_muted="#565A88",
    brand="#E11D48", brand_text="#C8102E", button="#C8102E", button_hover="#A80D27", on_button="#FFFFFF",
    success="#047857", warning="#92400E", danger="#B91C1C", info="#1D4ED8", shadow="0 1px 2px rgba(13,10,51,.10)",
)
PALETTES = {"dark": DARK, "light": LIGHT}


def palette(theme: str) -> Palette:
    return PALETTES.get(theme, DARK)


# ---------------------------------------------------------------- semantic + blood-group colours
KINDS = ("success", "warning", "danger", "info", "neutral")


def kind_style(kind: str, theme: str) -> tuple[str, str, str]:
    """(text, background, border) for a semantic kind; text is AA-readable on the tinted background."""
    p = palette(theme)
    base = {"success": p.success, "warning": p.warning, "danger": p.danger, "info": p.info, "neutral": p.text_muted}[kind]
    bg = p.tint(base, 0.14 if kind != "neutral" else 0.10)
    return p.readable(base, bg), bg, p.readable(base, p.bg_surface, 3.0)


# Okabe-Ito colour-blind-safe hues, one per ABO family. Colour is never the only cue: the label is always printed and
# Rh-negative badges are outlined while Rh-positive ones are filled.
ABO_HUES = {"A": "#0072B2", "B": "#E69F00", "AB": "#CC79A7", "O": "#009E73"}


def blood_style(group: str, theme: str) -> tuple[str, str, str, bool]:
    """(text, background, border, filled) for a blood-group badge."""
    family, positive = group[:-1], group.endswith("+")
    p = palette(theme)
    hue = ABO_HUES[family]
    bg = p.tint(hue, 0.20) if positive else p.bg_surface
    return p.readable(hue, bg), bg, hue, positive


BLOOD_HUE_KEYS = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")


def chart_colour(group: str) -> str:
    return ABO_HUES[group[:-1]]
