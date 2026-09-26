"""Small glue so pages can call a service and show its message instead of a traceback."""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from lifeline.errors import DomainError

logger = logging.getLogger("lifeline.actions")


def attempt(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[bool, str | None, Any]:
    """(ok, error message, result). Rule violations become messages; anything else is a real bug and propagates."""
    try:
        return True, None, fn(*args, **kwargs)
    except DomainError as exc:
        logger.info("%s rejected (%s): %s", getattr(fn, "__name__", "action"), type(exc).__name__, exc)
        return False, str(exc), None
