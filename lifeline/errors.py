"""Domain errors raised by services. Pages show str(error); nothing here carries PII."""
from __future__ import annotations


class DomainError(Exception):
    """A rule was broken; the operation changed nothing."""


class ValidationError(DomainError):
    pass


class NotFound(DomainError):
    pass


class InsufficientStock(DomainError):
    def __init__(self, blood_group: str, wanted: int, available: int):
        super().__init__(f"Only {available} unit(s) of {blood_group} available; {wanted} needed.")
        self.blood_group, self.wanted, self.available = blood_group, wanted, available


class IncompatibleBlood(DomainError):
    def __init__(self, unit_group: str, patient_group: str):
        super().__init__(f"{unit_group} blood is NOT compatible with a {patient_group} patient.")


class InvalidTransition(DomainError):
    pass
