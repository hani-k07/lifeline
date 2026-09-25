import pytest

from lifeline.auth import passwords as pw


def test_hash_is_bcrypt_salted_and_verifies():
    a, b = pw.hash_password("correct horse"), pw.hash_password("correct horse")
    assert a.startswith("$2") and a != b          # salted: same password, different hashes
    assert pw.verify_password("correct horse", a)
    assert not pw.verify_password("wrong horse!", a)


def test_policy():
    with pytest.raises(pw.PasswordPolicyError):
        pw.hash_password("short")
    with pytest.raises(pw.PasswordPolicyError):
        pw.hash_password("x" * 73)
    pw.hash_password("x" * 72)                     # boundary is allowed
    with pytest.raises(pw.PasswordPolicyError):
        pw.hash_password("é" * 40)                 # 80 bytes: length is measured in bytes, not characters


def test_legacy_sha256_still_verifies_and_is_flagged():
    legacy = pw.legacy_sha256("lifeline123")
    assert pw.is_legacy_sha256(legacy)
    assert pw.verify_password("lifeline123", legacy)
    assert not pw.verify_password("lifeline124", legacy)
    assert pw.needs_rehash(legacy)


def test_needs_rehash_tracks_cost(monkeypatch):
    from lifeline.config import get_settings

    cheap = pw.hash_password("correct horse")                # cost 4 (conftest)
    assert not pw.needs_rehash(cheap)
    monkeypatch.setenv("BCRYPT_ROUNDS", "5")
    get_settings.cache_clear()
    assert pw.needs_rehash(cheap)


@pytest.mark.parametrize("junk", ["", "not-a-hash", "$2b$04$tooshort", "0" * 63])
def test_malformed_stored_hash_never_verifies_or_raises(junk):
    assert pw.verify_password("anything", junk) is False


def test_upgraded_hash_refuses_overlong_passwords_instead_of_crashing():
    assert pw.upgraded_hash("x" * 100) is None
    assert pw.upgraded_hash("fine password") is not None
