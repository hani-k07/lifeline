from pathlib import Path

import pytest

from lifeline.auth import rbac, session
from lifeline.auth.roles import ALL_ROLES, Role, is_valid_role

PAGES_DIR = Path(__file__).resolve().parents[2] / "pages"


def test_access_table_covers_exactly_the_page_files():
    """A page added without an access entry would be closed to everyone; a stale entry is dead config."""
    on_disk = {p.name for p in PAGES_DIR.glob("*.py")}
    assert on_disk == set(rbac.PAGE_ACCESS)


def test_role_vocabulary():
    assert [r.value for r in ALL_ROLES] == ["super_admin", "hospital_admin", "staff"]
    assert is_valid_role("staff") and not is_valid_role("admin") and not is_valid_role("hospital")
    assert Role.SUPER_ADMIN == "super_admin"          # str-compatible for session/DB comparisons


@pytest.mark.parametrize(
    ("role", "expected"),
    [("super_admin", 10), ("hospital_admin", 9), ("staff", 8), ("admin", 0), ("", 0)],
)
def test_sidebar_links_per_role(role, expected):
    assert len(rbac.nav_links(role)) == expected


@pytest.mark.parametrize(
    ("page", "super_admin", "hospital_admin", "staff"),
    [
        ("pages/1_dashboard.py", True, True, True),
        ("pages/9_ai_center.py", True, True, False),
        ("pages/10_admin.py", True, False, False),
        ("pages/99_unknown.py", False, False, False),       # unknown page: closed
    ],
)
def test_can_access(page, super_admin, hospital_admin, staff):
    assert rbac.can_access("super_admin", page) is super_admin
    assert rbac.can_access("hospital_admin", page) is hospital_admin
    assert rbac.can_access("staff", page) is staff


def test_require_role_decorator(monkeypatch):
    state = {}
    monkeypatch.setattr(session.st, "session_state", state, raising=False)

    @rbac.require_role(Role.SUPER_ADMIN)
    def dangerous():
        return "done"

    with pytest.raises(PermissionError):                    # nobody signed in
        dangerous()
    state.update(logged_in=True, user_id=1, user_role="staff")
    with pytest.raises(PermissionError):
        dangerous()
    state["user_role"] = "super_admin"
    assert dangerous() == "done"
    state["user_role"] = "admin"                             # retired role name never matches
    with pytest.raises(PermissionError):
        dangerous()
