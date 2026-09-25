"""Password hashing (bcrypt) with transparent support for the legacy unsalted SHA-256 hashes."""
from __future__ import annotations

import hashlib
import hmac
import re
from functools import lru_cache

import bcrypt

from lifeline.config import get_settings

MIN_LENGTH = 8
MAX_BYTES = 72          # bcrypt ignores (v4) or rejects (v5) anything longer
_SHA256_HEX = re.compile(r"[0-9a-fA-F]{64}")


class PasswordPolicyError(ValueError):
    """The password is not acceptable for a new account or a change."""


def validate_password(password: str) -> None:
    if len(password) < MIN_LENGTH:
        raise PasswordPolicyError(f"Password must be at least {MIN_LENGTH} characters.")
    if len(password.encode("utf-8")) > MAX_BYTES:
        raise PasswordPolicyError(f"Password must be at most {MAX_BYTES} bytes.")


def _bcrypt(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(get_settings().bcrypt_rounds)).decode("ascii")


def hash_password(password: str) -> str:
    """Hash a new password. Raises PasswordPolicyError if it does not meet the policy."""
    validate_password(password)
    return _bcrypt(password)


def is_legacy_sha256(stored: str) -> bool:
    return bool(_SHA256_HEX.fullmatch(stored or ""))


def legacy_sha256(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, stored: str) -> bool:
    if is_legacy_sha256(stored):
        return hmac.compare_digest(legacy_sha256(password), stored.lower())
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored.encode("ascii"))
    except (ValueError, UnicodeError):
        return False


def needs_rehash(stored: str) -> bool:
    """True for legacy hashes and for bcrypt hashes cheaper than the configured cost."""
    if is_legacy_sha256(stored):
        return True
    try:
        return int(stored.split("$")[2]) < get_settings().bcrypt_rounds
    except (IndexError, ValueError):
        return True


def upgraded_hash(password: str) -> str | None:
    """A bcrypt hash for a password already verified against a legacy hash, or None if it can't be hashed
    (over-long passwords stay on the legacy hash until the user changes them)."""
    try:
        return _bcrypt(password)
    except ValueError:
        return None


@lru_cache(maxsize=4)
def _dummy_hash(rounds: int) -> str:
    return bcrypt.hashpw(b"lifeline-timing-dummy", bcrypt.gensalt(rounds)).decode("ascii")


def burn_time() -> None:
    """Spend one bcrypt verification so unknown-email logins take as long as real ones."""
    bcrypt.checkpw(b"not-the-password", _dummy_hash(get_settings().bcrypt_rounds).encode("ascii"))
