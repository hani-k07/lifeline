"""Demo accounts. Seeded by setup_database.py; only *shown* on the login page when APP_ENV=demo."""
from __future__ import annotations

from typing import NamedTuple

from lifeline.auth.roles import Role

DEMO_PASSWORD = "lifeline123"


class DemoUser(NamedTuple):
    email: str
    role: Role
    name: str
    hospital_id: int | None
    hospital: str


DEMO_USERS: tuple[DemoUser, ...] = (
    DemoUser("admin@lifeline.com", Role.SUPER_ADMIN, "Dr. Zara Ahmed (Admin)", None, "Global"),
    DemoUser("mayo@lifeline.com", Role.HOSPITAL_ADMIN, "Dr. Kamran Sheikh (Mayo)", 1, "Mayo Hospital"),
    DemoUser("services@lifeline.com", Role.HOSPITAL_ADMIN, "Dr. Amna Malik (Services)", 2, "Services Hospital"),
    DemoUser("jinnah@lifeline.com", Role.HOSPITAL_ADMIN, "Dr. Bilal Hassan (Jinnah)", 3, "Jinnah Hospital"),
    DemoUser("shaukat@lifeline.com", Role.HOSPITAL_ADMIN, "Dr. Sara Yousaf (Shaukat)", 4, "Shaukat Khanum"),
    DemoUser("mayo.worker@lifeline.com", Role.STAFF, "Nurse Hira Baig (Mayo)", 1, "Mayo Hospital"),
    DemoUser("mayo.worker2@lifeline.com", Role.STAFF, "Technician Saad Ali (Mayo)", 1, "Mayo Hospital"),
    DemoUser("services.worker@lifeline.com", Role.STAFF, "Nurse Rabia Naz (Services)", 2, "Services Hospital"),
    DemoUser("jinnah.worker@lifeline.com", Role.STAFF, "Technician Umar Farooq (Jinnah)", 3, "Jinnah Hospital"),
    DemoUser("shaukat.worker@lifeline.com", Role.STAFF, "Nurse Fatima Zia (Shaukat)", 4, "Shaukat Khanum"),
    DemoUser("shaukat.worker2@lifeline.com", Role.STAFF, "Technician Ali Hamza (Shaukat)", 4, "Shaukat Khanum"),
)
