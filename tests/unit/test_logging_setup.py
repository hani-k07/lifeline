import json
import logging

import pytest

from lifeline import logging_setup
from lifeline.config import get_settings


@pytest.fixture
def clean_logger():
    logger = logging.getLogger("lifeline")
    saved = (list(logger.handlers), logger.level, logger.propagate)
    logger.handlers.clear()
    yield logger
    for handler in logger.handlers:
        handler.close()
    logger.handlers[:] = saved[0]
    logger.setLevel(saved[1])
    logger.propagate = saved[2]


def lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_records_are_json_lines_in_the_file(clean_logger):
    logging_setup.configure_logging()
    logging.getLogger("lifeline.test").info("hello %s", "world")
    [entry] = lines(get_settings().log_file)
    assert entry["msg"] == "hello world" and entry["level"] == "INFO" and entry["logger"] == "lifeline.test"
    assert entry["ts"].endswith("+05:00")                                   # Pakistan time, like the audit log


def test_configuring_twice_does_not_duplicate_lines(clean_logger):
    logging_setup.configure_logging()
    logging_setup.configure_logging()
    logging.getLogger("lifeline.test").info("once")
    assert len(lines(get_settings().log_file)) == 1


@pytest.mark.parametrize("secret", [
    "35202-1234567-1", "0300-1234567", "someone@example.com", "sk-or-v1-abcdef0123456789",
    "$2b$12$" + "a" * 53, "Bearer abc.def.ghi",
])
def test_secrets_and_identifiers_never_reach_the_log(clean_logger, secret):
    logging_setup.configure_logging()
    logging.getLogger("lifeline.test").warning("failure with %s in it", secret)
    try:
        raise ValueError(f"bad value {secret}")
    except ValueError:
        logging.getLogger("lifeline.test").exception("boom")
    text = get_settings().log_file.read_text(encoding="utf-8")
    assert secret not in text and text.count("failure with") == 1
    assert "[SECRET]" in text or "[CNIC]" in text or "[PHONE]" in text or "[EMAIL]" in text


def test_an_unwritable_log_location_falls_back_to_the_console(clean_logger, monkeypatch, tmp_path):
    blocker = tmp_path / "file-not-dir"
    blocker.write_text("x")
    monkeypatch.setenv("LOG_FILE", str(blocker / "sub" / "app.log"))
    get_settings.cache_clear()
    logging_setup.configure_logging()                                       # must not raise
    assert len(clean_logger.handlers) == 1 and isinstance(clean_logger.handlers[0], logging.StreamHandler)


def test_failed_logins_are_logged_without_the_email(clean_logger, demo_db):
    from lifeline.auth.service import authenticate

    logging_setup.configure_logging()
    authenticate("admin@lifeline.com", "wrong-password")
    text = get_settings().log_file.read_text(encoding="utf-8")
    assert "login failed" in text and "admin@lifeline.com" not in text
