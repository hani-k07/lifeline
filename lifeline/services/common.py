from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Protocol

from lifeline.auth.roles import Role
from lifeline.constants import BLOOD_GROUPS
from lifeline.db.repositories import hospitals as hospitals_repo
from lifeline.errors import NotAuthorized, NotFound, ValidationError


class Actor(Protocol):
    """Who is acting. `session.CurrentUser` satisfies this; so does SYSTEM."""

    @property
    def id(self) -> int | None: ...
    @property
    def hospital_id(self) -> int | None: ...
    @property
    def is_super(self) -> bool: ...


@dataclass(frozen=True)
class SystemActor:
    id: int | None = None
    role: Role = Role.SUPER_ADMIN
    hospital_id: int | None = None
    is_super: bool = True


SYSTEM = SystemActor()


def authorize_hospital(actor: Actor, hospital_id: int) -> None:
    if not actor.is_super and actor.hospital_id != hospital_id:
        raise NotAuthorized("You can only act on your own hospital's data.")


def authorize_any(actor: Actor, *hospital_ids: int) -> None:
    if not actor.is_super and actor.hospital_id not in hospital_ids:
        raise NotAuthorized("You can only act on data that involves your own hospital.")


def check_group(blood_group: str) -> str:
    if blood_group not in BLOOD_GROUPS:
        raise ValidationError(f"Unknown blood group: {blood_group!r}.")
    return blood_group


def check_count(count: int, *, maximum: int, what: str = "units") -> int:
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ValidationError(f"Number of {what} must be at least 1.")
    if count > maximum:
        raise ValidationError(f"Number of {what} cannot exceed {maximum}.")
    return count


def require_hospital(conn: sqlite3.Connection, hospital_id: int) -> dict[str, Any]:
    hospital = hospitals_repo.get(conn, hospital_id)
    if hospital is None:
        raise NotFound(f"Hospital {hospital_id} does not exist.")
    return hospital
