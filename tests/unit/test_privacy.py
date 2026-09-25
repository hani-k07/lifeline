import pytest

from lifeline.privacy import mask_cnic, scrub_rows, scrub_text


@pytest.mark.parametrize(
    ("raw", "masked"),
    [
        ("35202-1234567-1", "35202-*******-1"),
        ("3520212345671", "35202-*******-1"),           # no dashes
        (None, "—"),
        ("", "—"),
        ("1234", "********"),                            # malformed: mask everything
    ],
)
def test_mask_cnic(raw, masked):
    assert mask_cnic(raw) == masked


def test_scrub_text_patterns():
    text = "Call 0300-1234567 or +92 321 7654321, cnic 35202-1234567-1, mail a.b@lifeline.com"
    out = scrub_text(text)
    assert "[PHONE]" in out and "[CNIC]" in out and "[EMAIL]" in out
    for leaked in ("0300", "7654321", "35202", "a.b@"):
        assert leaked not in out


def test_scrub_text_known_names_longest_first_case_insensitive():
    out = scrub_text("Transfused 2u to ali hassan. Ali was stable.", names=["Ali", "Ali Hassan"])
    assert out == "Transfused 2u to [NAME]. [NAME] was stable."


def test_scrub_text_strips_parenthetical_staff_suffix_and_respects_word_boundaries():
    out = scrub_text("Nurse Hira Baig recorded it; Baigan is a vegetable", names=["Nurse Hira Baig (Mayo)"])
    assert out.startswith("[NAME] recorded it") and "Baigan" in out


def test_scrub_rows_is_an_allow_list():
    rows = [{"id": 1, "patient_name": "Ali Hassan", "performed_by": "Dr Z", "units": 2,
             "notes": "Ali Hassan, cnic 35202-1234567-1"}]
    out = scrub_rows(rows, keep=("id", "units"), text_fields=("notes",), names=["Ali Hassan"])
    assert out == [{"id": 1, "units": 2, "notes": "[NAME], cnic [CNIC]"}]
    assert "patient_name" not in out[0] and "performed_by" not in out[0]
