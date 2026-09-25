"""The single role vocabulary. Stored in users.role and compared everywhere else."""
from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    SUPER_ADMIN = "super_admin"
    HOSPITAL_ADMIN = "hospital_admin"
    STAFF = "staff"

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").title()


ALL_ROLES: tuple[Role, ...] = (Role.SUPER_ADMIN, Role.HOSPITAL_ADMIN, Role.STAFF)
ADMIN_ROLES: tuple[Role, ...] = (Role.SUPER_ADMIN, Role.HOSPITAL_ADMIN)


def is_valid_role(value: object) -> bool:
    return value in {r.value for r in Role}
