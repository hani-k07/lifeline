"""Shared plumbing for engine operations: errors, PEAS descriptions, payload validation, and the registry."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


class EngineError(ValueError):
    """The input to an operation is invalid. Nothing was computed."""


@dataclass(frozen=True)
class Peas:
    """The PEAS description of the agent an operation implements."""

    performance: str
    environment: str
    actuators: str
    sensors: str


@dataclass(frozen=True)
class Operation:
    name: str
    func: Callable[[Mapping[str, Any]], dict[str, Any]]
    summary: str
    complexity: str
    peas: Peas
    used_by: str


OPERATIONS: dict[str, Operation] = {}


def register(name: str, *, summary: str, complexity: str, peas: Peas, used_by: str) -> Callable[[Callable[..., dict[str, Any]]], Callable[..., dict[str, Any]]]:
    def decorate(func: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
        if name in OPERATIONS:
            raise RuntimeError(f"engine operation {name!r} registered twice")
        OPERATIONS[name] = Operation(name, func, summary, complexity, peas, used_by)
        return func

    return decorate


def need(payload: Mapping[str, Any], key: str, kind: type | tuple[type, ...], what: str | None = None) -> Any:
    """Fetch a required key and check its type (bool is not accepted where a number is wanted)."""
    if key not in payload:
        raise EngineError(f"missing required field {key!r}")
    value = payload[key]
    numeric = kind in (int, float, (int, float))
    if not isinstance(value, kind) or (numeric and isinstance(value, bool)):
        raise EngineError(f"{what or key!r} must be {getattr(kind, '__name__', kind)}, got {type(value).__name__}")
    return value


def number(value: Any, name: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
        raise EngineError(f"{name} must be a number")
    if minimum is not None and value < minimum:
        raise EngineError(f"{name} must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise EngineError(f"{name} must be at most {maximum}")
    return float(value)
