"""Demand forecasting and shortage risk. Pure Python (the old version needed numpy + scikit-learn and read columns
that do not exist in the database).

Weighted moving average (WMA)  recent days count more; each forecast day feeds the next
    Complexity   O(window) per forecast day
Ordinary least squares trend   slope of usage per day
    Complexity   O(n)
Shortage risk                  cumulative forecast demand against current stock
    Complexity   O(horizon)

PEAS - supply planning agent
    Performance  a shortage is flagged early enough to reorder
    Environment  daily usage history and current stock, per blood group
    Actuators    risk level, days until stock-out, suggested reorder quantity
    Sensors      units issued/transfused per day (inventory event ledger), stock now
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


def _clean(history: Sequence[float]) -> list[float]:
    values = [float(v) for v in history]
    if any(v < 0 or v != v for v in values):
        raise ValueError("usage history cannot contain negative or missing values")
    return values


def wma_forecast(history: Sequence[float], horizon: int = 7, window: int = 7) -> list[float]:
    """Next `horizon` days of demand. An empty history forecasts zero demand."""
    if horizon < 1 or window < 1:
        raise ValueError("horizon and window must be at least 1")
    data = _clean(history)
    if not data:
        return [0.0] * horizon
    out: list[float] = []
    for _ in range(horizon):
        recent = data[-window:]
        weights = range(1, len(recent) + 1)
        value = sum(v * w for v, w in zip(recent, weights, strict=True)) / sum(weights)
        out.append(round(value, 2))
        data.append(value)
    return out


def linear_trend(history: Sequence[float]) -> float:
    """Least-squares slope in units per day (0 with fewer than two points)."""
    data = _clean(history)
    n = len(data)
    if n < 2:
        return 0.0
    mean_x, mean_y = (n - 1) / 2, sum(data) / n
    denom = sum((x - mean_x) ** 2 for x in range(n))
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(range(n), data, strict=True)) / denom


@dataclass(frozen=True)
class ShortageRisk:
    days_until_stockout: int | None      # None: stock outlasts the forecast horizon
    risk_level: str                      # CRITICAL | HIGH | MEDIUM | LOW
    recommended_reorder: int
    forecast_total: float


def shortage_risk(stock: float, forecast: Sequence[float], buffer: float = 1.5) -> ShortageRisk:
    """How soon does `stock` run out if demand follows `forecast`? `buffer` is the safety margin wanted."""
    if stock < 0:
        raise ValueError("stock cannot be negative")
    need = sum(forecast)
    if need <= 0:                                            # no demand expected: nothing to run out of
        return ShortageRisk(None, "LOW", 0, 0.0)
    days: int | None = None
    used = 0.0
    for day, demand in enumerate(forecast, start=1):
        used += demand
        if used >= stock:
            days = day - 1 if stock == 0 else day
            break
    reorder = max(0, math.ceil(buffer * need - stock))
    if days is not None and days <= 2:
        level = "CRITICAL"
    elif days is not None and days <= 5:
        level = "HIGH"
    elif stock < buffer * need:
        level = "MEDIUM"
    else:
        level = "LOW"
    return ShortageRisk(days, level, reorder, round(need, 2))


def predict_shortage(groups: Sequence[dict[str, Any]], horizon: int = 7, window: int = 7, buffer: float = 1.5) -> list[dict[str, Any]]:
    """One row per blood group: `groups` items carry blood_group, stock and the daily usage history."""
    rows = []
    for g in groups:
        history = _clean(g.get("history", []))
        forecast = wma_forecast(history, horizon, window)
        risk = shortage_risk(float(g["stock"]), forecast, buffer)
        slope = linear_trend(history)
        rows.append({
            "blood_group": g["blood_group"], "stock": g["stock"], "forecast": forecast,
            "avg_daily_demand": round(sum(history) / len(history), 2) if history else 0.0,
            "trend": "rising" if slope > 0.1 else "falling" if slope < -0.1 else "stable",
            "days_until_stockout": risk.days_until_stockout, "risk_level": risk.risk_level,
            "recommended_reorder": risk.recommended_reorder,
        })
    return rows
