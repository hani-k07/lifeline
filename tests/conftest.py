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


@pytest.fixture(scope="session")
def demo_template(tmp_path_factory):
    """A fully seeded demo database, built once per test session (bcrypt at minimum cost)."""
    import os
    import sqlite3

    from lifeline.db.schema import create_schema
    from scripts.seed_demo import seed_demo

    path = tmp_path_factory.mktemp("demo") / "demo.db"
    saved = {k: os.environ.get(k) for k in ("DB_PATH", "BCRYPT_ROUNDS")}
    os.environ.update(DB_PATH=str(path), BCRYPT_ROUNDS="4")
    get_settings.cache_clear()
    try:
        conn = sqlite3.connect(path)
        create_schema(conn)
        seed_demo(conn)
        conn.close()
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
    return path


@pytest.fixture
def demo_db(demo_template):
    """The seeded demo database, copied to this test's DB_PATH."""
    import shutil

    shutil.copy(demo_template, get_settings().db_path)
    return get_settings().db_path
