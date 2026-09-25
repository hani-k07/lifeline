"""Domain vocabulary shared by services, repositories and tests. The SQL CHECK constraints mirror these."""
from __future__ import annotations

from enum import Enum

BLOOD_GROUPS: tuple[str, ...] = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")

# Per blood group, per hospital: fewer available units than this is "low" / "critical".
LOW_UNITS = 8
CRITICAL_UNITS = 3
MAX_UNITS_PER_RECEIPT = 500
# Whole-hospital stock status (hospitals.stock_status).
HOSPITAL_CRITICAL_TOTAL = 20
HOSPITAL_LOW_TOTAL = 60
# Groups emergency care depends on (common ones + the universal donor). Scarcity of rare groups only makes a hospital 'low'.
KEY_GROUPS = ("A+", "B+", "O+", "O-")


class UnitStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    ISSUED = "issued"
    TRANSFUSED = "transfused"
    EXPIRED = "expired"
    DISCARDED = "discarded"


# available -> reserved -> issued/transfused, or -> expired/discarded. Mirrored by the DB trigger
# trg_units_state_machine; tests assert the two agree for every (from, to) pair.
ALLOWED_TRANSITIONS: dict[UnitStatus, frozenset[UnitStatus]] = {
    UnitStatus.AVAILABLE: frozenset({UnitStatus.RESERVED, UnitStatus.ISSUED, UnitStatus.TRANSFUSED,
                                     UnitStatus.EXPIRED, UnitStatus.DISCARDED}),
    UnitStatus.RESERVED: frozenset({UnitStatus.AVAILABLE, UnitStatus.ISSUED, UnitStatus.TRANSFUSED,
                                    UnitStatus.EXPIRED, UnitStatus.DISCARDED}),
    UnitStatus.ISSUED: frozenset({UnitStatus.TRANSFUSED, UnitStatus.DISCARDED}),
    UnitStatus.TRANSFUSED: frozenset(),
    UnitStatus.EXPIRED: frozenset(),
    UnitStatus.DISCARDED: frozenset(),
}


class RequestStatus(str, Enum):
    PENDING = "PENDING"
    RESERVED = "RESERVED"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class Urgency(str, Enum):
    CRITICAL = "CRITICAL"
    URGENT = "URGENT"
    ROUTINE = "ROUTINE"


class ExchangeStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ContractStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RETURNED = "RETURNED"
    BREACHED = "BREACHED"
    CANCELLED = "CANCELLED"


class EventType(str, Enum):
    RECEIVED = "received"
    RESERVED = "reserved"
    RELEASED = "released"
    ISSUED = "issued"
    TRANSFUSED = "transfused"
    EXPIRED = "expired"
    DISCARDED = "discarded"
    TRANSFERRED_OUT = "transferred_out"
    TRANSFERRED_IN = "transferred_in"
