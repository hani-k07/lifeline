"""One-time logging setup: JSON lines to the console and a rotating file. Secrets and personal identifiers are redacted."""
from __future__ import annotations

import json
import logging
import logging.handlers
import re

from lifeline import clock
from lifeline.config import get_settings
from lifeline.privacy import scrub_text

# API keys, bcrypt hashes and bearer tokens; scrub_text covers CNIC, phone and email.
_SECRET = re.compile(r"sk-or-[\w-]+|\$2[aby]\$\d\d\$[./A-Za-z0-9]{53}|(?i:bearer)\s+\S+")
_MARK = "_lifeline_handler"
MAX_BYTES, BACKUPS = 1_000_000, 5


def redact(text: str) -> str:
    return _SECRET.sub("[SECRET]", scrub_text(text))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {"ts": clock.now_iso(), "level": record.levelname, "logger": record.name, "msg": redact(record.getMessage())}
        if record.exc_info:
            entry["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(entry, ensure_ascii=False)


def configure_logging() -> None:
    """Attach the handlers to the 'lifeline' logger once per process. A log file that cannot be opened is not fatal."""
    logger = logging.getLogger("lifeline")
    if any(getattr(h, _MARK, False) for h in logger.handlers):
        return
    settings = get_settings()
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        settings.log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.handlers.RotatingFileHandler(settings.log_file, maxBytes=MAX_BYTES, backupCount=BACKUPS,
                                                             encoding="utf-8"))
    except OSError:
        logger.warning("log file %s is not writable; logging to the console only", settings.log_file)
    for handler in handlers:
        handler.setFormatter(JsonFormatter())
        setattr(handler, _MARK, True)
        logger.addHandler(handler)
    logger.setLevel(settings.log_level)
    logger.propagate = False
