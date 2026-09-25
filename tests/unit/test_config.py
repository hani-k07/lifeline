import pytest
from pydantic import ValidationError

from lifeline.config import Settings, get_settings


def test_defaults_are_safe():
    s = get_settings()
    assert s.app_env == "dev"          # demo conveniences are opt-in
    assert s.db_backend == "sqlite"
    assert s.ai_enabled is False


def test_secret_is_never_rendered(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-supersecret")
    get_settings.cache_clear()
    s = get_settings()
    assert s.ai_enabled is True
    assert "supersecret" not in repr(s)
    assert "supersecret" not in str(s.openrouter_api_key)


def test_supabase_backend_rejected_until_implemented():
    with pytest.raises(ValidationError):
        Settings(db_backend="supabase")


@pytest.mark.parametrize("field", ["session_timeout_minutes", "login_max_attempts", "bcrypt_rounds"])
def test_numeric_bounds(field):
    with pytest.raises(ValidationError):
        Settings(**{field: 0})
