"""One Plotly theme for every chart. Axes are always titled with units; there are no pie charts (eight slices are
unreadable); blood-group colours are the colour-blind-safe set and Rh-negative bars carry a hatch pattern."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import plotly.graph_objects as go
import streamlit as st

from lifeline.constants import BLOOD_GROUPS
from lifeline.ui import tokens as t
from lifeline.ui.theme import current_theme


def _apply(fig: go.Figure, *, title: str | None, height: int, x_title: str | None, y_title: str | None,
           legend: bool = True) -> go.Figure:
    p = t.palette(current_theme())
    fig.update_layout(
        title=dict(text=title, x=0, font=dict(size=15)) if title else None, height=height,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=8, r=8, t=44 if title else 12, b=8),
        font=dict(family=t.FONT_STACK, color=p.text_primary, size=13), showlegend=legend,
        legend=dict(orientation="h", y=-0.22, x=0, font=dict(color=p.text_secondary)),
        hoverlabel=dict(bgcolor=p.bg_elevated, font=dict(color=p.text_primary)),
    )
    fig.update_xaxes(title=dict(text=x_title, font=dict(color=p.text_secondary)) if x_title else None, gridcolor=p.border_subtle,
                     zerolinecolor=p.border_subtle, linecolor=p.border_subtle, tickfont=dict(color=p.text_secondary), automargin=True)
    fig.update_yaxes(title=dict(text=y_title, font=dict(color=p.text_secondary)) if y_title else None, gridcolor=p.border_subtle,
                     zerolinecolor=p.border_subtle, linecolor=p.border_subtle, tickfont=dict(color=p.text_secondary), automargin=True)
    return fig


def show(fig: go.Figure, **kwargs: Any) -> None:
    st.plotly_chart(fig, use_container_width=True, theme=None, config={"displayModeBar": False}, **kwargs)


def stock_bars(counts: Mapping[str, int], title: str | None = "Available units by blood group", height: int = 320) -> go.Figure:
    p = t.palette(current_theme())
    values = [int(counts.get(g, 0)) for g in BLOOD_GROUPS]
    fig = go.Figure(go.Bar(
        x=BLOOD_GROUPS, y=values, text=values, textposition="outside", cliponaxis=False,
        marker=dict(color=[t.chart_colour(g) for g in BLOOD_GROUPS],
                    pattern=dict(shape=["" if g.endswith("+") else "/" for g in BLOOD_GROUPS], bgcolor=p.bg_surface,
                                 fgcolor=p.text_primary, size=6, solidity=0.18),
                    line=dict(color=p.text_primary, width=1)),
        hovertemplate="%{x}: %{y} units<extra></extra>"))
    fig.update_yaxes(rangemode="tozero")
    return _apply(fig, title=title, height=height, x_title="Blood group (hatched = Rh negative)", y_title="Units available", legend=False)


def usage_forecast(history: Sequence[float], forecast: Sequence[float], title: str, height: int = 320) -> go.Figure:
    """`history` are the last full days (oldest first, ending yesterday); the forecast starts today (day 0)."""
    p = t.palette(current_theme())
    n = len(history)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(range(-n, 0)), y=list(history), name="Actual usage", mode="lines+markers",
                             line=dict(color=p.info, width=2)))
    fig.add_trace(go.Scatter(x=[-1, *range(0, len(forecast))], y=[history[-1] if history else 0, *forecast], name="Forecast",
                             mode="lines+markers", line=dict(color=p.brand_text, width=2, dash="dash")))
    fig.update_yaxes(rangemode="tozero")
    fig = _apply(fig, title=title or None, height=height, x_title="Days from today (0 = today)", y_title="Units per day")
    fig.update_layout(margin=dict(l=48, r=8, t=8 if not title else 44, b=8), legend=dict(orientation="h", y=1.12, x=0))
    return fig


def route_map(hospitals: Sequence[Mapping[str, Any]], edges: Sequence[tuple[float, float, float, float]] = (),
              route: Sequence[tuple[float, float]] = (), height: int = 380) -> go.Figure:
    """Hospitals as markers coloured by stock status (the status word is in the hover text), road links in grey, and the
    chosen route drawn thick in the brand red."""
    p = t.palette(current_theme())
    colours = {"critical": p.danger, "low": p.warning, "ok": p.success}
    fig = go.Figure()
    for lat1, lon1, lat2, lon2 in edges:
        fig.add_trace(go.Scattermap(lat=[lat1, lat2], lon=[lon1, lon2], mode="lines", line=dict(width=1.5, color=p.text_muted),
                                    hoverinfo="skip", showlegend=False))
    if route:
        fig.add_trace(go.Scattermap(lat=[r[0] for r in route], lon=[r[1] for r in route], mode="lines",
                                    line=dict(width=6, color=p.brand), name="Route", hoverinfo="skip"))
    fig.add_trace(go.Scattermap(
        lat=[h["latitude"] for h in hospitals], lon=[h["longitude"] for h in hospitals], mode="markers",
        marker=dict(size=13, color=[colours.get(h.get("stock_status", "ok"), p.info) for h in hospitals]),
        text=[f"{h['name']} - stock {h.get('stock_status', 'ok')}" for h in hospitals], hoverinfo="text", name="Hospitals"))
    pts = list(route) or [(h["latitude"], h["longitude"]) for h in hospitals] or [(31.52, 74.34)]
    fig.update_layout(map=dict(style="carto-darkmatter" if p.name == "dark" else "carto-positron",
                               center=dict(lat=sum(x[0] for x in pts) / len(pts), lon=sum(x[1] for x in pts) / len(pts)), zoom=10.6),
                      height=height, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      legend=dict(orientation="h", y=1.02, font=dict(color=p.text_primary)), font=dict(family=t.FONT_STACK))
    return fig


def group_level_bars(rows: Sequence[Mapping[str, Any]], value_field: str, title: str, y_title: str, height: int = 300) -> go.Figure:
    """A generic horizontal bar chart of (blood_group, value) rows."""
    p = t.palette(current_theme())
    groups = [r["blood_group"] for r in rows]
    fig = go.Figure(go.Bar(y=groups, x=[r[value_field] for r in rows], orientation="h",
                           marker=dict(color=[t.chart_colour(g) for g in groups], line=dict(color=p.text_primary, width=1)),
                           text=[r[value_field] for r in rows], textposition="outside", cliponaxis=False))
    fig.update_yaxes(autorange="reversed")
    return _apply(fig, title=title, height=height, x_title=y_title, y_title="Blood group", legend=False)
