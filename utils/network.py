"""The hospital road graph, built once per process and reused by every page."""
from __future__ import annotations

from collections.abc import Sequence

import streamlit as st

from lifeline.engine.graph import Graph, Node, build_road_graph


@st.cache_resource(show_spinner=False)
def _build(nodes: tuple[tuple[int, str, float, float], ...]) -> Graph:
    return build_road_graph([Node(*n) for n in nodes])


def get_road_graph(hospitals: Sequence[dict]) -> Graph:
    """Sparse road network (k=3 nearest neighbours x 1.3 road factor). Cached on the hospitals' ids and coordinates,
    so it is rebuilt only when a hospital is added or moved."""
    return _build(tuple((h["id"], h["name"], float(h["latitude"]), float(h["longitude"])) for h in hospitals
                        if h.get("latitude") is not None and h.get("longitude") is not None))
