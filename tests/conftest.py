import pytest

from lifeline.config import Settings, get_settings


@pytest.fixture(autouse=True)
def fresh_settings(monkeypatch, tmp_path):
    """Every test gets its own DB path, cheap bcrypt and an uncached Settings object."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)   # never read the developer's real .env
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
