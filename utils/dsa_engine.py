"""
Pure Python DSA + AI engine for LIFELINE blood logistics.

All algorithms expose JSON-in / JSON-out via run_engine().
"""

from __future__ import annotations

import heapq
import random
from collections import deque
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.preprocessing import StandardScaler


def _require_keys(payload: dict, keys: list[str], fn_name: str) -> None:
    """Validate required payload keys exist."""
    missing = [k for k in keys if k not in payload]
    if missing:
        raise ValueError(f"{fn_name}: missing required keys: {missing}")


def dijkstra(payload: dict) -> dict:
    """
    Dijkstra's shortest path to nearest available hospital.

    Algorithm: Dijkstra single-source shortest path with min-heap.
    Time Complexity: O((V + E) log V)
    Space Complexity: O(V)
    PEAS:
        Performance: Minimizes total route distance in km.
        Environment: Weighted hospital network graph.
        Actuators: Returns optimal path and distance table.
        Sensors: source_id, hospitals, edges, available_hospitals.
    Use Case: Emergency blood routing to nearest hospital with stock.

    Args:
        payload: {source_id, hospitals, edges, available_hospitals}.

    Returns:
        {best_hospital, best_hospital_name, distance, path, all_distances}.
    """
    _require_keys(payload, ["source_id", "hospitals", "edges"], "dijkstra")
    source_id: str = payload["source_id"]
    hospitals: list[dict] = payload.get("hospitals", [])
    edges: list[dict] = payload.get("edges", [])
    available: set[str] = set(payload.get("available_hospitals", []))

    name_map = {h["id"]: h.get("name", h["id"]) for h in hospitals}

    adj: dict[str, list[tuple[str, float]]] = {}
    for e in edges:
        adj.setdefault(e["from"], []).append((e["to"], float(e["weight"])))

    dist: dict[str, float] = {source_id: 0.0}
    prev: dict[str, str | None] = {source_id: None}
    pq: list[tuple[float, str]] = [(0.0, source_id)]
    visited: set[str] = set()

    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        for v, w in adj.get(u, []):
            nd = d + w
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))

    candidates = [hid for hid in available if hid in dist and hid != source_id]
    if not candidates:
        return {
            "best_hospital": None,
            "best_hospital_name": None,
            "distance": None,
            "path": [],
            "all_distances": dist,
        }

    best = min(candidates, key=lambda h: dist[h])
    path: list[str] = []
    cur: str | None = best
    while cur is not None:
        path.append(cur)
        cur = prev.get(cur)
    path.reverse()

    return {
        "best_hospital": best,
        "best_hospital_name": name_map.get(best, best),
        "distance": round(dist[best], 2),
        "path": path,
        "all_distances": {k: round(v, 2) for k, v in dist.items()},
    }


def bfs_backup(payload: dict) -> dict:
    """
    BFS backup hospital discovery ordered by hop count.

    Algorithm: Breadth-first search with level tracking.
    Time Complexity: O(V + E)
    Space Complexity: O(V)
    PEAS:
        Performance: Finds nearest backup nodes by hop count.
        Environment: Hospital adjacency graph.
        Actuators: Ranked backup hospital list.
        Sensors: source_id, hospitals, edges, exclude_ids.
    Use Case: Secondary routing when primary hospital is unavailable.

    Args:
        payload: {source_id, hospitals, edges, exclude_ids}.

    Returns:
        {backup_hospitals: [{id, name, level, distance_km}]}.
    """
    _require_keys(payload, ["source_id", "hospitals", "edges"], "bfs_backup")
    source_id: str = payload["source_id"]
    hospitals: list[dict] = payload.get("hospitals", [])
    edges: list[dict] = payload.get("edges", [])
    exclude: set[str] = set(payload.get("exclude_ids", []))

    name_map = {h["id"]: h.get("name", h["id"]) for h in hospitals}
    adj: dict[str, list[tuple[str, float]]] = {}
    for e in edges:
        adj.setdefault(e["from"], []).append((e["to"], float(e["weight"])))

    level: dict[str, int] = {source_id: 0}
    dist_km: dict[str, float] = {source_id: 0.0}
    queue: deque[str] = deque([source_id])
    backup: list[dict] = []

    while queue:
        u = queue.popleft()
        for v, w in adj.get(u, []):
            if v in exclude or v in level:
                continue
            level[v] = level[u] + 1
            dist_km[v] = dist_km[u] + w
            queue.append(v)
            if v != source_id:
                backup.append({
                    "id": v,
                    "name": name_map.get(v, v),
                    "level": level[v],
                    "distance_km": round(dist_km[v], 2),
                })

    backup.sort(key=lambda x: (x["level"], x["distance_km"]))
    return {"backup_hospitals": backup}


def fefo_sort(payload: dict) -> dict:
    """
    First-Expired-First-Out sorting via min-heap on expiry date.

    Algorithm: Heap sort (min-heap on expiry_date).
    Time Complexity: O(n log n)
    Space Complexity: O(n)
    PEAS:
        Performance: Prioritizes units closest to expiry.
        Environment: Blood inventory warehouse.
        Actuators: Sorted dispatch queue.
        Sensors: Unit records with expiry_date and status.
    Use Case: Inventory rotation to minimize wastage.

    Args:
        payload: {units: [{id, blood_group, component, expiry_date, status, ...}]}.

    Returns:
        {sorted_units, expiring_soon, total_units, available_units}.
    """
    units: list[dict] = payload.get("units", [])
    available = [u for u in units if u.get("status") == "available"]
    total_units = len(units)
    available_units = len(available)

    heap: list[tuple[str, int, dict]] = []
    for i, u in enumerate(available):
        exp = str(u.get("expiry_date", "9999-12-31"))
        heapq.heappush(heap, (exp, i, u))

    sorted_units: list[dict] = []
    while heap:
        _, _, unit = heapq.heappop(heap)
        sorted_units.append(unit)

    today = date.today()
    expiring_soon: list[dict] = []
    for u in sorted_units:
        try:
            exp = date.fromisoformat(str(u["expiry_date"])[:10])
            if 0 <= (exp - today).days <= 7:
                expiring_soon.append(u)
        except (ValueError, KeyError, TypeError):
            pass

    return {
        "sorted_units": sorted_units,
        "expiring_soon": expiring_soon,
        "total_units": total_units,
        "available_units": available_units,
    }


def merge_sort(payload: dict) -> dict:
    """
    Recursive merge sort on contract return deadlines.

    Algorithm: Divide-and-conquer merge sort.
    Time Complexity: O(n log n)
    Space Complexity: O(n)
    PEAS:
        Performance: Chronological contract ordering.
        Environment: Active lending contract registry.
        Actuators: Sorted contract list with compliance counts.
        Sensors: Contract records with return_deadline ISO strings.
    Use Case: Contract deadline management and breach detection.

    Args:
        payload: {contracts: [{id, return_deadline, status, ...}]}.

    Returns:
        {sorted_contracts, overdue_count, active_count}.
    """
    contracts: list[dict] = payload.get("contracts", [])
    now = datetime.now()

    def _merge_sort(arr: list[dict]) -> list[dict]:
        if len(arr) <= 1:
            return arr
        mid = len(arr) // 2
        left = _merge_sort(arr[:mid])
        right = _merge_sort(arr[mid:])
        merged: list[dict] = []
        i = j = 0
        while i < len(left) and j < len(right):
            dl = str(left[i].get("return_deadline", ""))
            dr = str(right[j].get("return_deadline", ""))
            if dl <= dr:
                merged.append(left[i])
                i += 1
            else:
                merged.append(right[j])
                j += 1
        merged.extend(left[i:])
        merged.extend(right[j:])
        return merged

    sorted_contracts = _merge_sort(list(contracts))
    overdue_count = 0
    active_count = 0
    for c in sorted_contracts:
        if c.get("status") == "active":
            active_count += 1
            try:
                deadline = datetime.fromisoformat(str(c["return_deadline"]))
                if deadline < now:
                    overdue_count += 1
            except (ValueError, TypeError):
                pass

    return {
        "sorted_contracts": sorted_contracts,
        "overdue_count": overdue_count,
        "active_count": active_count,
    }


def exchange_match(payload: dict) -> dict:
    """
    Hash-map blood exchange matching in O(n).

    Algorithm: Hash table inverse lookup.
    Time Complexity: O(n)
    Space Complexity: O(n)
    PEAS:
        Performance: O(1) lookup per offer for inverse match.
        Environment: Inter-hospital exchange pool.
        Actuators: Matched pair assignments.
        Sensors: Pending exchange offers.
    Use Case: ABO-compatible cross-hospital blood swaps.

    Args:
        payload: {offers: [{id, offering_hospital_id, offered_blood_group,
                  requested_blood_group, units, status}]}.

    Returns:
        {matched_pairs, unmatched}.
    """
    offers: list[dict] = payload.get("offers", [])
    pending = [o for o in offers if o.get("status") == "pending"]

    index: dict[str, list[dict]] = {}
    for o in pending:
        key = o.get("requested_blood_group", "")
        index.setdefault(key, []).append(o)

    matched_pairs: list[dict] = []
    matched_ids: set[str] = set()

    for offer in pending:
        oid = offer.get("id", "")
        if oid in matched_ids:
            continue
        offered = offer.get("offered_blood_group", "")
        candidates = index.get(offered, [])
        for other in candidates:
            if other.get("id") == oid or other.get("id") in matched_ids:
                continue
            if (other.get("requested_blood_group") == offered
                    and other.get("offered_blood_group") == offer.get("requested_blood_group")):
                if other.get("offering_hospital_id") != offer.get("offering_hospital_id"):
                    matched_pairs.append({
                        "offer_a": offer,
                        "offer_b": other,
                        "blood_group_a": offer.get("offered_blood_group"),
                        "blood_group_b": other.get("offered_blood_group"),
                    })
                    matched_ids.add(oid)
                    matched_ids.add(other.get("id", ""))
                    break

    unmatched = [o for o in pending if o.get("id") not in matched_ids]
    return {"matched_pairs": matched_pairs, "unmatched": unmatched}


def risk_score(payload: dict) -> dict:
    """
    Hill-climbing donor risk scoring with penalty annealing.

    Algorithm: Iterative penalty application (hill climbing heuristic).
    Time Complexity: O(r) where r = number of rules
    Space Complexity: O(r)
    PEAS:
        Performance: Quantifies donor eligibility risk 0-100.
        Environment: Donor health screening context.
        Actuators: Classification and penalty breakdown.
        Sensors: Donor vitals, diseases, donation history.
    Use Case: Pre-screening risk assessment before expert system.

    Args:
        payload: {donor: {age, last_donation_days, diseases, on_blood_thinners,
                  hemoglobin, bp_systolic, ...}}.

    Returns:
        {score, classification, penalties, recommendation}.
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

    if any(x in disease_str for x in ("hiv", "hepatitis b", "hepb", "hepatitis c", "hepc")):
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
        apply("Age Restriction", -20, f"Age {age} outside 18-65 range")

    hb = donor.get("hemoglobin", 14.0)
    if hb < 12.5:
        apply("Low Hemoglobin", -15, f"Hemoglobin {hb} g/dL below 12.5")

    if "diabetes" in disease_str or donor.get("diabetes"):
        apply("Diabetes", -10, "Diabetes mellitus reported")

    bp_sys = donor.get("bp_systolic", 120)
    if bp_sys > 160:
        apply("Hypertension", -10, f"Systolic BP {bp_sys} > 160 mmHg")

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


def screen_donor(payload: dict) -> dict:
    """
    Forward-chaining expert system for donor screening.

    Algorithm: Priority-ordered rule-based inference (forward chaining).
    Time Complexity: O(r) where r = number of rules
    Space Complexity: O(r)
    PEAS:
        Performance: Highest-priority fired rule determines outcome.
        Environment: Clinical screening workstation.
        Actuators: SAFE/DEFER/BLOCK decision with rule trace.
        Sensors: Donor vitals and serology markers.
    Use Case: Automated donor eligibility determination.

    Args:
        payload: {donor: {hemoglobin, bp_systolic, bp_diastolic, pulse,
                  temperature, weight, hiv, hepb, hepc, syphilis, malaria, diseases}}.

    Returns:
        {decision, fired_rules, inference_chain}.
    """
    donor: dict = payload.get("donor", {})
    diseases = [d.lower() for d in donor.get("diseases", [])]
    disease_str = " ".join(diseases)

    rules: list[dict] = [
        {"rule_name": "HIV_Positive", "priority": 1,
         "check": lambda: donor.get("hiv") or "hiv" in disease_str,
         "decision": "BLOCK", "reason": "HIV positive — permanent deferral"},
        {"rule_name": "HepB_Positive", "priority": 2,
         "check": lambda: donor.get("hepb") or "hepb" in disease_str or "hepatitis b" in disease_str,
         "decision": "BLOCK", "reason": "Hepatitis B positive — permanent deferral"},
        {"rule_name": "HepC_Positive", "priority": 3,
         "check": lambda: donor.get("hepc") or "hepc" in disease_str or "hepatitis c" in disease_str,
         "decision": "BLOCK", "reason": "Hepatitis C positive — permanent deferral"},
        {"rule_name": "Syphilis_Positive", "priority": 4,
         "check": lambda: donor.get("syphilis"),
         "decision": "BLOCK", "reason": "Syphilis positive — defer until treated"},
        {"rule_name": "Malaria_Positive", "priority": 5,
         "check": lambda: donor.get("malaria"),
         "decision": "DEFER", "reason": "Malaria positive — defer 3 years post-treatment"},
        {"rule_name": "Low_Hemoglobin", "priority": 6,
         "check": lambda: donor.get("hemoglobin", 14) < 12.5,
         "decision": "DEFER", "reason": "Hemoglobin below 12.5 g/dL minimum"},
        {"rule_name": "High_BP_Systolic", "priority": 7,
         "check": lambda: donor.get("bp_systolic", 120) > 180,
         "decision": "DEFER", "reason": "Systolic BP exceeds 180 mmHg"},
        {"rule_name": "Low_BP_Systolic", "priority": 8,
         "check": lambda: donor.get("bp_systolic", 120) < 90,
         "decision": "DEFER", "reason": "Systolic BP below 90 mmHg"},
        {"rule_name": "High_Pulse", "priority": 9,
         "check": lambda: donor.get("pulse", 72) > 100,
         "decision": "DEFER", "reason": "Pulse rate exceeds 100 bpm"},
        {"rule_name": "Fever", "priority": 10,
         "check": lambda: donor.get("temperature", 37.0) > 37.5,
         "decision": "DEFER", "reason": "Elevated temperature — possible infection"},
        {"rule_name": "Low_Weight", "priority": 11,
         "check": lambda: donor.get("weight", 60) < 50,
         "decision": "DEFER", "reason": "Weight below 50 kg minimum"},
        {"rule_name": "All_Clear", "priority": 12,
         "check": lambda: True,
         "decision": "SAFE", "reason": "All screening parameters within acceptable limits"},
    ]

    inference_chain: list[str] = []
    fired_rules: list[dict] = []
    decision = "SAFE"

    for rule in sorted(rules, key=lambda r: r["priority"]):
        inference_chain.append(f"Evaluating rule {rule['rule_name']} (priority {rule['priority']})")
        if rule["check"]():
            fired_rules.append({
                "rule_name": rule["rule_name"],
                "priority": rule["priority"],
                "reason": rule["reason"],
            })
            inference_chain.append(f"FIRED: {rule['rule_name']} → {rule['decision']}")
            decision = rule["decision"]
            if rule["priority"] <= 5:
                break
        else:
            inference_chain.append(f"Skipped: {rule['rule_name']} — condition not met")

    if not fired_rules:
        fired_rules.append({"rule_name": "All_Clear", "priority": 12,
                            "reason": "No rules triggered — default SAFE"})
        decision = "SAFE"

    return {"decision": decision, "fired_rules": fired_rules, "inference_chain": inference_chain}


def transfusion_monitor(payload: dict) -> dict:
    """
    Model-based reflex agent for transfusion reaction monitoring.

    Algorithm: Threshold-based reflex rules on vital deltas.
    Time Complexity: O(1)
    Space Complexity: O(1)
    PEAS:
        Performance: Real-time adverse reaction classification.
        Environment: Active transfusion session.
        Actuators: STOP/SLOW/CONTINUE commands with severity.
        Sensors: Pre and post transfusion vitals.
    Use Case: Detect anaphylaxis, hemolytic, and febrile reactions.

    Args:
        payload: {pre: {temp, bp_systolic, bp_diastolic, pulse, o2_sat},
                  post: {same fields}}.

    Returns:
        {reaction_type, severity, action, deltas, alert_color}.
    """
    pre: dict = payload.get("pre", {})
    post: dict = payload.get("post", {})

    temp_rise = post.get("temp", 37.0) - pre.get("temp", 37.0)
    bp_drop = pre.get("bp_systolic", 120) - post.get("bp_systolic", 120)
    o2_change = post.get("o2_sat", 98) - pre.get("o2_sat", 98)

    deltas = {
        "temp_rise": round(temp_rise, 2),
        "bp_drop": round(bp_drop, 2),
        "o2_change": round(o2_change, 2),
    }

    o2_post = post.get("o2_sat", 98)

    if o2_post < 90 and bp_drop > 40:
        return {
            "reaction_type": "ANAPHYLAXIS",
            "severity": "CRITICAL",
            "action": "STOP TRANSFUSION IMMEDIATELY. CODE BLUE.",
            "deltas": deltas,
            "alert_color": "red",
        }
    if temp_rise > 2.0 and bp_drop > 30:
        return {
            "reaction_type": "HEMOLYTIC",
            "severity": "SEVERE",
            "action": "STOP transfusion. Send sample for DAT. Monitor renal function.",
            "deltas": deltas,
            "alert_color": "red",
        }
    if temp_rise > 1.0:
        return {
            "reaction_type": "FEBRILE",
            "severity": "MODERATE",
            "action": "SLOW transfusion rate. Administer antipyretic. Monitor closely.",
            "deltas": deltas,
            "alert_color": "amber",
        }
    return {
        "reaction_type": "NORMAL",
        "severity": "NONE",
        "action": "Transfusion proceeding normally. Continue monitoring.",
        "deltas": deltas,
        "alert_color": "green",
    }


def predict_shortage(payload: dict) -> dict:
    """
    Linear regression blood shortage forecasting per blood group.

    Algorithm: Linear regression on daily stock counts.
    Time Complexity: O(n * g) where g = blood groups
    Space Complexity: O(n)
    PEAS:
        Performance: 7-day stock projection per group.
        Environment: Hospital blood bank inventory.
        Actuators: Risk-level alerts per blood group.
        Sensors: Historical unit records with dates.
    Use Case: Proactive shortage prevention planning.

    Args:
        payload: {units: [{blood_group, collection_date, expiry_date, status}]}.

    Returns:
        {predictions: [{blood_group, current_stock, predicted_7d, trend, risk_level}]}.
    """
    units: list[dict] = payload.get("units", [])
    today = date.today()
    groups = sorted({u.get("blood_group", "?") for u in units})
    predictions: list[dict] = []

    for bg in groups:
        bg_units = [u for u in units if u.get("blood_group") == bg]
        current_stock = sum(1 for u in bg_units if u.get("status") == "available")

        daily_counts: dict[int, int] = {}
        for u in bg_units:
            if u.get("status") != "available":
                continue
            try:
                col = date.fromisoformat(str(u.get("collection_date", today.isoformat()))[:10])
                day_offset = (today - col).days
                if 0 <= day_offset <= 30:
                    daily_counts[day_offset] = daily_counts.get(day_offset, 0) + 1
            except (ValueError, TypeError):
                pass

        if len(daily_counts) >= 2:
            xs = np.array(list(daily_counts.keys())).reshape(-1, 1)
            ys = np.array(list(daily_counts.values()))
            model = LinearRegression()
            model.fit(xs, ys)
            predicted_7d = max(0, int(model.predict([[7]])[0]))
            slope = float(model.coef_[0])
        else:
            predicted_7d = current_stock
            slope = 0.0

        if slope > 0.1:
            trend = "rising"
        elif slope < -0.1:
            trend = "falling"
        else:
            trend = "stable"

        if predicted_7d < 3:
            risk_level = "CRITICAL"
        elif predicted_7d < 8:
            risk_level = "HIGH"
        elif predicted_7d < 15:
            risk_level = "MODERATE"
        else:
            risk_level = "LOW"

        predictions.append({
            "blood_group": bg,
            "current_stock": current_stock,
            "predicted_7d": predicted_7d,
            "trend": trend,
            "risk_level": risk_level,
        })

    return {"predictions": predictions}


def cluster_donors(payload: dict) -> dict:
    """
    K-Means donor segmentation into ELITE / REGULAR / HIGH_RISK.

    Algorithm: K-Means clustering (k=3) on normalized features.
    Time Complexity: O(n * k * i) where i = iterations
    Space Complexity: O(n)
    PEAS:
        Performance: Groups donors by engagement and risk profile.
        Environment: Donor registry database.
        Actuators: Cluster labels and summary statistics.
        Sensors: Donor demographic and donation history features.
    Use Case: Targeted donor outreach and retention campaigns.

    Args:
        payload: {donors: [{id, name, age, times_donated, risk_score,
                  last_donation_days, blood_group}]}.

    Returns:
        {clusters, cluster_summary}.
    """
    donors: list[dict] = payload.get("donors", [])
    if not donors:
        return {"clusters": [], "cluster_summary": []}

    features = []
    for d in donors:
        features.append([
            float(d.get("age", 30)),
            float(d.get("times_donated", 0)),
            float(d.get("risk_score", 50)),
            float(d.get("last_donation_days", 180)),
        ])

    X = np.array(features)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    k = min(3, len(donors))
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)
    centroids = scaler.inverse_transform(kmeans.cluster_centers_)

    cluster_labels_map: dict[int, str] = {}
    for cid in range(k):
        c = centroids[cid]
        risk = c[2]
        freq = c[1]
        if risk >= 70 and freq >= 3:
            cluster_labels_map[cid] = "ELITE"
        elif risk < 50 or c[3] > 365:
            cluster_labels_map[cid] = "HIGH_RISK"
        else:
            cluster_labels_map[cid] = "REGULAR"

    clusters: list[dict] = []
    for i, d in enumerate(donors):
        cid = int(labels[i])
        clusters.append({
            "donor_id": d.get("id"),
            "donor_name": d.get("name", d.get("full_name", "Unknown")),
            "cluster_label": cluster_labels_map.get(cid, "REGULAR"),
            "cluster_id": cid,
        })

    summary: list[dict] = []
    for cid in range(k):
        members = [c for c in clusters if c["cluster_id"] == cid]
        summary.append({
            "cluster_id": cid,
            "label": cluster_labels_map.get(cid, "REGULAR"),
            "count": len(members),
            "avg_risk": round(float(centroids[cid][2]), 1),
            "avg_donations": round(float(centroids[cid][1]), 1),
        })

    return {"clusters": clusters, "cluster_summary": summary}


def naive_bayes_classify(payload: dict) -> dict:
    """
    Gaussian Naive Bayes donor eligibility classifier.

    Algorithm: Gaussian Naive Bayes with synthetic priors fallback.
    Time Complexity: O(n * f) training, O(f) prediction
    Space Complexity: O(n * f)
    PEAS:
        Performance: Probabilistic eligibility prediction.
        Environment: Donor screening training dataset.
        Actuators: Eligible/ineligible classification with confidence.
        Sensors: Feature vectors [age, hemoglobin, bp_systolic].
    Use Case: ML-assisted donor eligibility screening.

    Args:
        payload: {training_data: [[features...], ...], input_features: [age, hb, bp]}.

    Returns:
        {prediction, confidence, probabilities}.
    """
    training: list = payload.get("training_data", [])
    input_features: list = payload.get("input_features", [25, 13.0, 120])

    if not training:
        training = [
            [22, 14.0, 118, 1], [35, 13.5, 125, 1], [28, 15.0, 110, 1],
            [45, 14.5, 130, 1], [30, 13.8, 120, 1],
            [19, 11.0, 140, 0], [70, 12.0, 170, 0], [25, 10.5, 115, 0],
            [55, 11.5, 165, 0], [40, 12.2, 155, 0],
        ]

    X = np.array([row[:-1] if len(row) > 3 else row for row in training])
    if X.ndim == 1:
        X = X.reshape(1, -1)
    y = np.array([row[-1] if len(row) > 3 else 1 for row in training])

    if len(set(y)) < 2:
        y = np.array([1, 0, 1, 0, 1, 0, 1, 0, 1, 0][: len(y)])

    clf = GaussianNB()
    clf.fit(X, y)
    probs = clf.predict_proba([input_features])[0]
    classes = clf.classes_
    pred_idx = int(np.argmax(probs))
    prediction = "eligible" if classes[pred_idx] == 1 else "ineligible"

    return {
        "prediction": prediction,
        "confidence": round(float(probs[pred_idx]), 3),
        "probabilities": {
            "eligible": round(float(probs[list(classes).index(1)]) if 1 in classes else 0.5, 3),
            "ineligible": round(float(probs[list(classes).index(0)]) if 0 in classes else 0.5, 3),
        },
    }


def waste_minimize(payload: dict) -> dict:
    """
    Hill-climbing optimization to minimize blood unit wastage.

    Algorithm: Hill climbing with random swap neighborhood search.
    Time Complexity: O(iterations * n * m)
    Space Complexity: O(n + m)
    PEAS:
        Performance: Minimizes expired unused volume.
        Environment: Blood bank with patient demand queue.
        Actuators: Optimal unit-to-patient assignments.
        Sensors: Available units and patient volume requirements.
    Use Case: Reduce wastage by matching units to demand efficiently.

    Args:
        payload: {units: [...], patient_requirements: [{blood_group, volume_needed}]}.

    Returns:
        {optimal_assignment, estimated_waste_ml, iterations_run}.
    """
    units: list[dict] = payload.get("units", [])
    requirements: list[dict] = payload.get("patient_requirements", [])
    today = date.today()

    def waste(assignments: list[tuple]) -> float:
        used_ids = {a[0] for a in assignments}
        total_waste = 0.0
        for u in units:
            uid = u.get("id")
            if uid not in used_ids:
                try:
                    exp = date.fromisoformat(str(u["expiry_date"])[:10])
                    if exp < today + timedelta(days=7):
                        total_waste += float(u.get("volume_ml", 0))
                except (ValueError, KeyError, TypeError):
                    total_waste += float(u.get("volume_ml", 0))
        return total_waste

    available = [u for u in units if u.get("status", "available") == "available"]
    assignment: list[tuple] = []
    for req in requirements:
        bg = req.get("blood_group")
        vol_needed = float(req.get("volume_needed", 350))
        candidates = [u for u in available if u.get("blood_group") == bg]
        candidates.sort(key=lambda u: str(u.get("expiry_date", "")))
        if candidates:
            assignment.append((candidates[0]["id"], bg, vol_needed))

    best = list(assignment)
    best_waste = waste(best)
    iterations = 200

    for _ in range(iterations):
        if len(available) < 2 or not requirements:
            break
        new_assign = list(best)
        idx = random.randint(0, len(requirements) - 1) if requirements else 0
        bg = requirements[idx].get("blood_group")
        candidates = [u for u in available if u.get("blood_group") == bg]
        if len(candidates) < 2:
            continue
        u1, u2 = random.sample(candidates, 2)
        new_assign = [(u2["id"] if a[0] == u1["id"] else a[0], a[1], a[2]) for a in best]
        new_waste = waste(new_assign)
        if new_waste <= best_waste:
            best = new_assign
            best_waste = new_waste

    optimal_assignment = [
        {"unit_id": a[0], "blood_group": a[1], "volume_assigned_ml": a[2]}
        for a in best
    ]
    return {
        "optimal_assignment": optimal_assignment,
        "estimated_waste_ml": round(best_waste, 1),
        "iterations_run": iterations,
    }


def _triangular(x: float, a: float, b: float, c: float) -> float:
    """Triangular membership function."""
    if x <= a or x >= c:
        return 0.0
    if x == b:
        return 1.0
    if x < b:
        return (x - a) / (b - a) if b != a else 0.0
    return (c - x) / (c - b) if c != b else 0.0


def fuzzy_severity(payload: dict) -> dict:
    """
    Fuzzy logic severity scoring via triangular membership functions.

    Algorithm: Fuzzy inference with centroid defuzzification.
    Time Complexity: O(1)
    Space Complexity: O(1)
    PEAS:
        Performance: Continuous severity score 0-100.
        Environment: Transfusion reaction assessment.
        Actuators: MILD/MODERATE/SEVERE/CRITICAL label.
        Sensors: Vital sign deltas.
    Use Case: Graded severity assessment complementing reflex monitor.

    Args:
        payload: {temp_rise, bp_drop, o2_drop, pulse_change}.

    Returns:
        {severity_score, severity_label, membership_values}.
    """
    temp_rise = float(payload.get("temp_rise", 0))
    bp_drop = float(payload.get("bp_drop", 0))
    o2_drop = float(payload.get("o2_drop", 0))
    pulse_change = abs(float(payload.get("pulse_change", 0)))

    membership_values = {
        "temp_mild": _triangular(temp_rise, 0, 0.5, 1.0),
        "temp_severe": _triangular(temp_rise, 1.0, 2.0, 3.5),
        "bp_mild": _triangular(bp_drop, 0, 15, 30),
        "bp_severe": _triangular(bp_drop, 25, 40, 60),
        "o2_mild": _triangular(o2_drop, 0, 3, 6),
        "o2_severe": _triangular(o2_drop, 5, 10, 15),
        "pulse_mild": _triangular(pulse_change, 0, 10, 20),
        "pulse_severe": _triangular(pulse_change, 15, 30, 50),
    }

    mild_score = (
        membership_values["temp_mild"] * 25
        + membership_values["bp_mild"] * 25
        + membership_values["o2_mild"] * 25
        + membership_values["pulse_mild"] * 25
    ) / 4

    severe_score = (
        membership_values["temp_severe"] * 90
        + membership_values["bp_severe"] * 90
        + membership_values["o2_severe"] * 90
        + membership_values["pulse_severe"] * 90
    ) / 4

    severity_score = round(min(100, max(0, mild_score * 0.4 + severe_score * 0.6)), 1)

    if severity_score >= 80:
        severity_label = "CRITICAL"
    elif severity_score >= 55:
        severity_label = "SEVERE"
    elif severity_score >= 30:
        severity_label = "MODERATE"
    else:
        severity_label = "MILD"

    return {
        "severity_score": severity_score,
        "severity_label": severity_label,
        "membership_values": {k: round(v, 3) for k, v in membership_values.items()},
    }


def run_engine(operation: str, payload: dict) -> dict:
    """
    Master dispatcher for all DSA/AI operations.

    Args:
        operation: Algorithm name string.
        payload: Operation-specific input dict.

    Returns:
        Algorithm result dict or error dict.
    """
    ops = {
        "dijkstra": dijkstra,
        "bfs_backup": bfs_backup,
        "fefo_sort": fefo_sort,
        "merge_sort": merge_sort,
        "exchange_match": exchange_match,
        "risk_score": risk_score,
        "screen_donor": screen_donor,
        "transfusion_monitor": transfusion_monitor,
        "predict_shortage": predict_shortage,
        "cluster_donors": cluster_donors,
        "naive_bayes_classify": naive_bayes_classify,
        "waste_minimize": waste_minimize,
        "fuzzy_severity": fuzzy_severity,
    }
    if operation not in ops:
        return {"error": f"Unknown operation: {operation}"}
    try:
        return ops[operation](payload)
    except Exception as e:
        return {"error": str(e), "operation": operation}
