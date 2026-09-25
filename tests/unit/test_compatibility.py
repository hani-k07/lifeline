import pytest

from lifeline.constants import BLOOD_GROUPS
from lifeline.engine import compatibility as c


def reference(donor: str, recipient: str) -> bool:
    """Textbook rule, written independently of the table: the donor must not carry an antigen
    (A, B, RhD) that the recipient lacks."""
    d_abo, d_rh = donor[:-1], donor[-1]
    r_abo, r_rh = recipient[:-1], recipient[-1]
    antigens_ok = set(d_abo.replace("O", "")) <= set(r_abo.replace("O", ""))
    rh_ok = d_rh == "-" or r_rh == "+"
    return antigens_ok and rh_ok


@pytest.mark.parametrize("donor", BLOOD_GROUPS)
@pytest.mark.parametrize("recipient", BLOOD_GROUPS)
def test_all_64_pairs_match_the_reference_rule(donor, recipient):
    assert c.can_donate(donor, recipient) is reference(donor, recipient)


def test_known_clinical_facts():
    assert c.can_donate("O-", "AB+") and c.can_donate("O-", "A+")          # universal donor
    assert c.can_donate("AB+", "AB+") and not c.can_donate("AB+", "O+")
    assert not c.can_donate("A+", "A-") and not c.can_donate("O+", "O-")   # Rh+ never to Rh-
    assert not c.can_donate("A-", "B-") and not c.can_donate("B+", "A+")   # ABO mismatch
    assert c.compatible_donor_groups("O-") == ("O-",)
    assert len(c.compatible_donor_groups("AB+")) == 8


def test_recipient_and_donor_views_are_consistent():
    for donor in BLOOD_GROUPS:
        for recipient in c.compatible_recipient_groups(donor):
            assert donor in c.compatible_donor_groups(recipient)


def test_ranking_prefers_exact_then_saves_universal_donor_for_last():
    assert c.rank_donor_groups("A+") == ["A+", "A-", "O+", "O-"]
    assert c.rank_donor_groups("AB+")[0] == "AB+" and c.rank_donor_groups("AB+")[-1] == "O-"
    assert c.rank_donor_groups("O-") == ["O-"]


def test_unknown_group_is_an_error_not_false():
    with pytest.raises(ValueError):
        c.can_donate("X+", "A+")
    with pytest.raises(ValueError):
        c.can_donate("A+", "")
