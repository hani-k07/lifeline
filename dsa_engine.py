# dsa_engine.py
"""
LIFELINE v6.0 — Pure Python DSA Engine
Replaces all C++ logic. No subprocess. No .exe.
"""
from __future__ import annotations
import heapq
import math
from collections import defaultdict
from typing import Optional


# ─────────────────────────────────────────────
#  SECTION 1: GRAPH + DIJKSTRA (Hospital Network)
# ─────────────────────────────────────────────

class HospitalGraph:
    """
    Weighted undirected graph of hospitals.
    Edge weight = Haversine distance in km.
    """

    def __init__(self):
        self.nodes: dict[int, dict] = {}          # hospital_id → {name, lat, lon}
        self.edges: dict[int, list] = defaultdict(list)  # hospital_id → [(weight, neighbor_id)]

    def add_hospital(self, hospital_id: int, name: str, lat: float, lon: float) -> None:
        self.nodes[hospital_id] = {"name": name, "lat": lat, "lon": lon}

    @staticmethod
    def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Returns distance in km between two GPS coordinates."""
        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def build_full_mesh(self) -> None:
        """Connect every hospital to every other hospital (complete graph)."""
        ids = list(self.nodes.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                dist = self.haversine(
                    self.nodes[a]["lat"], self.nodes[a]["lon"],
                    self.nodes[b]["lat"], self.nodes[b]["lon"],
                )
                self.edges[a].append((dist, b))
                self.edges[b].append((dist, a))

    def dijkstra(self, source: int) -> tuple[dict[int, float], dict[int, Optional[int]]]:
        """
        Returns (distances, predecessors) from source to all other hospitals.
        distances[node] = shortest distance in km
        predecessors[node] = previous node on shortest path
        """
        dist = {node: float("inf") for node in self.nodes}
        prev: dict[int, Optional[int]] = {node: None for node in self.nodes}
        dist[source] = 0.0
        heap = [(0.0, source)]

        while heap:
            d, u = heapq.heappop(heap)
            if d > dist[u]:
                continue
            for weight, v in self.edges[u]:
                alt = dist[u] + weight
                if alt < dist[v]:
                    dist[v] = alt
                    prev[v] = u
                    heapq.heappush(heap, (alt, v))

        return dist, prev

    def shortest_path(self, source: int, target: int) -> tuple[list[int], float]:
        """Returns (path as list of hospital IDs, total distance in km)."""
        dist, prev = self.dijkstra(source)
        path = []
        cur: Optional[int] = target
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        if not path or path[0] != source:
            return [], float("inf")   # no path
        return path, round(dist[target], 2)

    def nearest_hospitals_with_blood(
        self, source: int, blood_group: str, inventory: list[dict]
    ) -> list[dict]:
        """
        Given source hospital + required blood group,
        returns ranked list of hospitals that have that blood group,
        sorted by Dijkstra distance from source.
        inventory = list of dicts with keys: hospital_id, blood_group, units
        """
        dist, _ = self.dijkstra(source)
        available = {}
        for item in inventory:
            if item["blood_group"] == blood_group and item["units"] > 0:
                hid = item["hospital_id"]
                if hid != source:
                    available[hid] = available.get(hid, 0) + item["units"]

        results = []
        for hid, units in available.items():
            path, km = self.shortest_path(source, hid)
            results.append({
                "hospital_id": hid,
                "hospital_name": self.nodes.get(hid, {}).get("name", str(hid)),
                "distance_km": km,
                "units_available": units,
                "path": path,
            })
        return sorted(results, key=lambda x: x["distance_km"])


# ─────────────────────────────────────────────
#  SECTION 2: PRIORITY QUEUE (Emergency Triage)
# ─────────────────────────────────────────────

class TriageQueue:
    """
    Min-heap priority queue for blood requests.
    Lower priority number = higher urgency.
    Priority levels: 1=CRITICAL, 2=URGENT, 3=ROUTINE
    """

    def __init__(self):
        self._heap: list = []
        self._counter = 0   # tiebreaker

    def push(self, priority: int, request: dict) -> None:
        heapq.heappush(self._heap, (priority, self._counter, request))
        self._counter += 1

    def pop(self) -> dict:
        if not self._heap:
            raise IndexError("Triage queue is empty")
        _, _, request = heapq.heappop(self._heap)
        return request

    def peek(self) -> dict | None:
        if not self._heap:
            return None
        return self._heap[0][2]

    def all_sorted(self) -> list[dict]:
        return [item[2] for item in sorted(self._heap)]

    def __len__(self) -> int:
        return len(self._heap)

    def is_empty(self) -> bool:
        return len(self._heap) == 0


# ─────────────────────────────────────────────
#  SECTION 3: BLOOD COMPATIBILITY MATCHING
# ─────────────────────────────────────────────

# Standard ABO + Rh compatibility matrix
# can_receive[recipient] = set of donor types that are compatible
BLOOD_COMPATIBILITY: dict[str, list[str]] = {
    "A+":  ["A+", "A-", "O+", "O-"],
    "A-":  ["A-", "O-"],
    "B+":  ["B+", "B-", "O+", "O-"],
    "B-":  ["B-", "O-"],
    "AB+": ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],
    "AB-": ["A-", "B-", "AB-", "O-"],
    "O+":  ["O+", "O-"],
    "O-":  ["O-"],
}

BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]


def get_compatible_donors(recipient_group: str) -> list[str]:
    """Returns list of blood groups that can donate to the recipient."""
    return BLOOD_COMPATIBILITY.get(recipient_group, [])


def get_compatible_recipients(donor_group: str) -> list[str]:
    """Returns list of blood groups that can receive from this donor."""
    return [r for r, donors in BLOOD_COMPATIBILITY.items() if donor_group in donors]


def find_best_match(
    patient_blood_group: str,
    available_inventory: list[dict],
    prefer_exact: bool = True,
) -> list[dict]:
    """
    Scores and ranks available blood units for a patient.
    Returns sorted list with best matches first.
    Score: exact match = 100, compatible = 50 - (compatibility distance).
    Penalizes units close to expiry.
    """
    compatible = get_compatible_donors(patient_blood_group)
    results = []

    for unit in available_inventory:
        if unit["blood_group"] not in compatible:
            continue
        score = 100 if unit["blood_group"] == patient_blood_group else 60
        # Prefer units expiring sooner (FIFO — reduce wastage)
        days_to_expiry = unit.get("days_to_expiry", 999)
        if days_to_expiry < 3:
            score -= 20   # nearly expired — deprioritise slightly
        elif days_to_expiry < 7:
            score += 10   # expiring soon — use these first
        results.append({**unit, "match_score": score})

    return sorted(results, key=lambda x: (-x["match_score"], x.get("days_to_expiry", 999)))


# ─────────────────────────────────────────────
#  SECTION 4: DEMAND FORECASTING (Moving Average)
# ─────────────────────────────────────────────

def forecast_demand(
    historical_usage: list[float],
    window: int = 7,
    forecast_days: int = 7,
) -> list[float]:
    """
    Simple weighted moving average forecast.
    historical_usage: list of daily units used (most recent last)
    Returns list of forecasted values for next `forecast_days` days.
    """
    if len(historical_usage) < window:
        window = max(1, len(historical_usage))

    forecasts = []
    data = list(historical_usage)

    for _ in range(forecast_days):
        recent = data[-window:]
        weights = list(range(1, len(recent) + 1))
        wma = sum(v * w for v, w in zip(recent, weights)) / sum(weights)
        forecasts.append(round(wma, 1))
        data.append(wma)

    return forecasts


def detect_shortage_risk(
    current_stock: float,
    forecast: list[float],
    safety_buffer: float = 1.5,
) -> dict:
    """
    Given current stock and a usage forecast,
    returns days until stockout and risk level.
    """
    cumulative = 0.0
    days_until_stockout = len(forecast)  # assume stock lasts full period if enough

    for i, daily_usage in enumerate(forecast):
        cumulative += daily_usage
        if cumulative >= current_stock:
            days_until_stockout = i + 1
            break

    needed_for_buffer = sum(forecast) * safety_buffer
    risk = "LOW"
    if days_until_stockout <= 2:
        risk = "CRITICAL"
    elif days_until_stockout <= 5:
        risk = "HIGH"
    elif current_stock < needed_for_buffer:
        risk = "MEDIUM"

    return {
        "days_until_stockout": days_until_stockout,
        "risk_level": risk,
        "recommended_reorder": max(0, round(needed_for_buffer - current_stock, 1)),
    }


# ─────────────────────────────────────────────
#  SECTION 5: GRAPH FACTORY (builds from DB data)
# ─────────────────────────────────────────────

def build_hospital_graph(hospitals: list[dict]) -> HospitalGraph:
    """
    Builds and returns a fully-connected HospitalGraph from a list of hospital dicts.
    Each dict must have: id, name, latitude, longitude
    """
    g = HospitalGraph()
    for h in hospitals:
        g.add_hospital(h["id"], h["name"], h["latitude"], h["longitude"])
    g.build_full_mesh()
    return g


# ─────────────────────────────────────────────
#  SECTION 6: EXPERT SYSTEM — DONOR SCREENING
# ─────────────────────────────────────────────

def screen_donor(payload: dict) -> dict:
    """
    Forward-chaining expert system for donor screening.

    Algorithm: Priority-ordered rule-based inference (forward chaining).
    Time Complexity: O(r) where r = number of rules
    PEAS: Actuators: SAFE/DEFER/BLOCK decision with rule trace.
    """
    donor: dict = payload.get("donor", {})
    diseases = [d.lower() for d in donor.get("diseases", [])]
    disease_str = " ".join(diseases)

    rules: list[dict] = [
        {"rule_name": "HIV_Positive",    "priority": 1,
         "check": lambda: donor.get("hiv") or "hiv" in disease_str,
         "decision": "BLOCK", "reason": "HIV positive — permanent deferral"},
        {"rule_name": "HepB_Positive",   "priority": 2,
         "check": lambda: donor.get("hepb") or "hepb" in disease_str or "hepatitis b" in disease_str,
         "decision": "BLOCK", "reason": "Hepatitis B positive — permanent deferral"},
        {"rule_name": "HepC_Positive",   "priority": 3,
         "check": lambda: donor.get("hepc") or "hepc" in disease_str or "hepatitis c" in disease_str,
         "decision": "BLOCK", "reason": "Hepatitis C positive — permanent deferral"},
        {"rule_name": "Syphilis_Positive","priority": 4,
         "check": lambda: donor.get("syphilis"),
         "decision": "BLOCK", "reason": "Syphilis positive — defer until treated"},
        {"rule_name": "Malaria_Positive", "priority": 5,
         "check": lambda: donor.get("malaria"),
         "decision": "DEFER", "reason": "Malaria positive — defer 3 years post-treatment"},
        {"rule_name": "Low_Hemoglobin",  "priority": 6,
         "check": lambda: donor.get("hemoglobin", 14) < 12.5,
         "decision": "DEFER", "reason": "Hemoglobin below 12.5 g/dL minimum"},
        {"rule_name": "High_BP_Systolic","priority": 7,
         "check": lambda: donor.get("bp_systolic", 120) > 180,
         "decision": "DEFER", "reason": "Systolic BP exceeds 180 mmHg"},
        {"rule_name": "Low_BP_Systolic", "priority": 8,
         "check": lambda: donor.get("bp_systolic", 120) < 90,
         "decision": "DEFER", "reason": "Systolic BP below 90 mmHg"},
        {"rule_name": "Low_Weight",      "priority": 9,
         "check": lambda: donor.get("weight", 60) < 50,
         "decision": "DEFER", "reason": "Weight below 50 kg minimum"},
        {"rule_name": "All_Clear",       "priority": 10,
         "check": lambda: True,
         "decision": "SAFE", "reason": "All screening parameters within acceptable limits"},
    ]

    inference_chain: list[str] = []
    fired_rules: list[dict] = []
    decision = "SAFE"

    for rule in sorted(rules, key=lambda r: r["priority"]):
        inference_chain.append(f"Evaluating {rule['rule_name']} (priority {rule['priority']})")
        if rule["check"]():
            fired_rules.append({
                "rule_name": rule["rule_name"],
                "priority":  rule["priority"],
                "reason":    rule["reason"],
            })
            inference_chain.append(f"FIRED: {rule['rule_name']} → {rule['decision']}")
            decision = rule["decision"]
            if rule["priority"] <= 5:
                break
        else:
            inference_chain.append(f"Skipped: {rule['rule_name']}")

    if not fired_rules:
        fired_rules.append({"rule_name": "All_Clear", "priority": 10,
                            "reason": "No rules triggered — default SAFE"})
        decision = "SAFE"

    return {"decision": decision, "fired_rules": fired_rules, "inference_chain": inference_chain}


def risk_score(payload: dict) -> dict:
    """
    Hill-climbing donor risk scoring with penalty annealing.
    Returns {score, classification, penalties, recommendation}.
    """
    donor: dict = payload.get("donor", {})
    score = 100
    penalties: list[dict] = []

    def apply(rule: str, deduction: int, reason: str) -> None:
        nonlocal score
        score += deduction
        penalties.append({"rule": rule, "deduction": deduction, "reason": reason})

    diseases = [d.lower() for d in donor.get("diseases", [])]
    disease_str = " ".join(diseases)

    if any(x in disease_str for x in ("hiv", "hepatitis b", "hepatitis c")):
        apply("Infectious Disease", -100, "HIV/HepB/HepC detected — instant fail")
    if donor.get("hiv") or donor.get("hepb") or donor.get("hepc"):
        apply("Serology Positive", -100, "Positive serology marker")
    if donor.get("on_blood_thinners"):
        apply("Blood Thinners", -30, "Patient on anticoagulant therapy")

    last_days = donor.get("last_donation_days", 999)
    if last_days < 90:
        apply("Recent Donation", -15, f"Last donation {last_days} days ago (< 90)")

    age = donor.get("age", 30)
    if age < 18 or age > 65:
        apply("Age Restriction", -20, f"Age {age} outside 18–65 range")

    hb = donor.get("hemoglobin", 14.0)
    if hb < 12.5:
        apply("Low Hemoglobin", -15, f"Hemoglobin {hb} g/dL below 12.5")

    bp_sys = donor.get("bp_systolic", 120)
    if bp_sys > 160:
        apply("Hypertension", -10, f"Systolic BP {bp_sys} > 160 mmHg")

    if donor.get("weight", 60) < 50:
        apply("Low Weight", -10, "Body weight below 50 kg minimum")

    score = max(0, score)
    if score <= 0 or any(p["deduction"] == -100 for p in penalties):
        classification = "BLOCK"
        recommendation = "Donor is not eligible. Defer indefinitely pending medical review."
    elif score < 70:
        classification = "DEFER"
        recommendation = "Donor should be deferred. Address flagged conditions and re-screen."
    else:
        classification = "SAFE"
        recommendation = "Donor meets risk thresholds. Proceed to full expert screening."

    return {
        "score": score,
        "classification": classification,
        "penalties": penalties,
        "recommendation": recommendation,
    }


def transfusion_monitor(payload: dict) -> dict:
    """
    Model-based reflex agent for transfusion reaction monitoring.
    Returns {reaction_type, severity, action, deltas, alert_color}.
    """
    pre: dict = payload.get("pre", {})
    post: dict = payload.get("post", {})

    temp_rise = post.get("temp", 37.0) - pre.get("temp", 37.0)
    bp_drop   = pre.get("bp_systolic", 120) - post.get("bp_systolic", 120)
    o2_change = post.get("o2_sat", 98) - pre.get("o2_sat", 98)
    o2_post   = post.get("o2_sat", 98)

    deltas = {
        "temp_rise": round(temp_rise, 2),
        "bp_drop":   round(bp_drop, 2),
        "o2_change": round(o2_change, 2),
    }

    if o2_post < 90 and bp_drop > 40:
        return {"reaction_type": "ANAPHYLAXIS",  "severity": "CRITICAL",
                "action": "STOP TRANSFUSION IMMEDIATELY. CODE BLUE.",
                "deltas": deltas, "alert_color": "red"}
    if temp_rise > 2.0 and bp_drop > 30:
        return {"reaction_type": "HEMOLYTIC",    "severity": "SEVERE",
                "action": "STOP transfusion. Send sample for DAT. Monitor renal function.",
                "deltas": deltas, "alert_color": "red"}
    if temp_rise > 1.0:
        return {"reaction_type": "FEBRILE",      "severity": "MODERATE",
                "action": "SLOW transfusion rate. Administer antipyretic. Monitor closely.",
                "deltas": deltas, "alert_color": "amber"}
    return {"reaction_type": "NORMAL", "severity": "NONE",
            "action": "Transfusion proceeding normally. Continue monitoring.",
            "deltas": deltas, "alert_color": "green"}

