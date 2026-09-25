"""Turns tokens into the stylesheet and injects it. The CSS lives in theme.css with $placeholders."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from string import Template

import streamlit as st

from lifeline.ui import tokens as t

_CSS = Path(__file__).with_name("theme.css")


def variables(theme: str) -> dict[str, str]:
    p = t.palette(theme)
    values = {k: str(v) for k, v in vars(p).items()}
    for kind in ("success", "warning", "danger", "info", "neutral"):
        text, bg, _ = t.kind_style(kind, theme)
        values[f"{kind}_text"], values[f"{kind}_bg"] = text, bg
    values.update(font=t.FONT_STACK, mono=t.MONO_STACK, scheme=theme)
    return values


@lru_cache(maxsize=2)
def css(theme: str) -> str:
    return Template(_CSS.read_text(encoding="utf-8")).substitute(variables(theme))


def current_theme() -> str:
    return "light" if st.session_state.get("theme") == "light" else "dark"


def inject(theme: str | None = None) -> None:
    st.markdown(f"<style>{css(theme or current_theme())}</style>", unsafe_allow_html=True)
