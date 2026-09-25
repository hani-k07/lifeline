"""Create the first (or another) super admin: python -m lifeline.auth.create_admin"""
from __future__ import annotations

import getpass
import sys

from lifeline.auth.roles import Role
from lifeline.auth.service import create_user
from lifeline.db.migrate import DatabaseNotInitialised, ensure_schema


def main() -> int:
    try:
        ensure_schema()
    except DatabaseNotInitialised as exc:
        print(exc)
        return 1
    email = input("Email: ").strip()
    name = input("Full name: ").strip()
    password = getpass.getpass("Password (min 8 characters): ")
    if password != getpass.getpass("Repeat password: "):
        print("Passwords do not match.")
        return 1
    ok, message = create_user(email, name, password, Role.SUPER_ADMIN.value, None, None)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
