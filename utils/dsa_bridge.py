import subprocess
import json
import os
import platform

def get_engine_path():
    if platform.system() == "Windows":
        return "./dsa_engine.exe"
    return "./dsa_engine"

def call_dsa(operation: str, data: dict) -> dict:
    data["operation"] = operation
    engine = get_engine_path()
    if not os.path.exists(engine):
        return {"error": f"DSA engine not found at '{engine}'. Please compile dsa_engine.exe first (see run.bat)."}
    try:
        result = subprocess.run(
            [engine],
            input=json.dumps(data),
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip() or "Engine returned non-zero exit code"}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"error": "DSA engine timed out (>10s). Check input data."}
    except json.JSONDecodeError:
        return {"error": f"Could not parse engine output: {result.stdout[:200]}"}
    except Exception as e:
        return {"error": str(e)}

# ─────────────────────────────────────────────
# HOSPITAL GRAPH — Lahore geography
# ─────────────────────────────────────────────

def get_hospital_graph():
    """
    Returns (hospitals_list, edges_list) for Dijkstra/BFS.
    Edges are distances in km between Lahore hospitals.
    """
    from utils.supabase_client import get_hospitals
    hospitals = get_hospitals()

    # Named edges based on real Lahore distances
    name_to_id = {h["name"]: h["id"] for h in hospitals}

    raw_edges = [
        ("Mayo Hospital",    "Services Hospital",  4.2),
        ("Mayo Hospital",    "Jinnah Hospital",    5.8),
        ("Services Hospital","Shaukat Khanum",     9.1),
        ("Jinnah Hospital",  "Shaukat Khanum",     7.3),
        ("Services Hospital","Jinnah Hospital",    3.6),
        ("Mayo Hospital",    "Shaukat Khanum",    11.2),
    ]

    edges = []
    for a, b, dist in raw_edges:
        id_a = name_to_id.get(a)
        id_b = name_to_id.get(b)
        if id_a and id_b:
            edges.append({"from": id_a, "to": id_b, "distance": dist})
            edges.append({"from": id_b, "to": id_a, "distance": dist})

    hospital_nodes = [
        {"id": h["id"], "name": h["name"],
         "lat": h.get("lat", 31.5), "lng": h.get("lng", 74.3),
         "city": h.get("city","Lahore")}
        for h in hospitals
    ]

    return hospital_nodes, edges

# ─────────────────────────────────────────────
# DSA OPERATIONS
# ─────────────────────────────────────────────

def fefo_sort(units: list) -> list:
    """Min-Heap FEFO: sort units by expiry date ascending."""
    if not units:
        return []
    result = call_dsa("fefo_sort", {"units": units})
    if "error" in result:
        # Graceful fallback: pure Python sort by expiry
        return sorted(units, key=lambda u: u.get("expiry_date", "9999"))
    return result.get("sorted_units", units)

def dijkstra(hospitals, edges, source_id: str,
             blood_group: str, available_hospitals: list) -> dict:
    """Dijkstra shortest path from source to nearest available hospital."""
    if not hospitals or not source_id:
        return {"error": "Missing hospital data"}
    result = call_dsa("dijkstra", {
        "hospitals": hospitals,
        "edges": edges,
        "source_id": source_id,
        "blood_group": blood_group,
        "available_hospitals": available_hospitals
    })
    if "error" in result:
        # Fallback: return first available hospital
        if available_hospitals:
            return {
                "best_hospital_id": available_hospitals[0],
                "distance": 0,
                "path": [source_id, available_hospitals[0]],
                "error": result["error"]
            }
    return result

def bfs_backup(hospitals, edges, source_id: str, available_hospitals: list) -> list:
    """BFS to find backup hospitals in order of graph distance."""
    result = call_dsa("bfs_backup", {
        "hospitals": hospitals,
        "edges": edges,
        "source_id": source_id,
        "available_hospitals": available_hospitals
    })
    if "error" in result:
        return available_hospitals[:3]
    return result.get("backups", [])

def find_exchange_match(new_offer: dict, existing_offers: list) -> dict:
    """HashMap O(1) matching: find hospital with complementary offer."""
    result = call_dsa("find_exchange_match", {
        "new_offer": new_offer,
        "existing_offers": existing_offers
    })
    if "error" in result:
        # Python fallback
        for o in existing_offers:
            if (o.get("offered_blood_group") == new_offer.get("needs_blood_group") and
                o.get("requested_blood_group") == new_offer.get("has_blood_group")):
                return {"matched": True, "matched_offer": o}
        return {"matched": False}
    return result

def calculate_risk_score(age: int, diseases: str,
                         days_since_donation: int,
                         on_blood_thinners: int) -> dict:
    """Calculate donor eligibility risk score (0-100)."""
    result = call_dsa("risk_score", {
        "age": age,
        "diseases": diseases,
        "days_since_donation": days_since_donation,
        "on_blood_thinners": on_blood_thinners
    })
    if "error" in result:
        # Python fallback risk calculation
        score = 100
        if age < 18 or age > 65:
            score -= 50
        disease_list = [d.strip().lower() for d in diseases.split(",") if d.strip()]
        if any(d in ["hiv","hepb","hepatitis b","hepatitis c","hepc"] for d in disease_list):
            score = 0
        if "diabetes" in disease_list:
            score -= 20
        if "hypertension" in disease_list:
            score -= 15
        if on_blood_thinners:
            score -= 30
        if days_since_donation < 90:
            score -= 20
        score = max(0, score)
        status = "SAFE" if score >= 80 else ("CAUTION" if score >= 50 else "BLOCKED")
        return {"score": score, "status": status, "penalties": [], "rules_fired": []}
    return result

def screen_donor(donor_data: dict) -> dict:
    """Full donor screening via expert system rules."""
    result = call_dsa("screen_donor", {"donor": donor_data})
    if "error" in result:
        # Fallback: simple rule check
        blocked_tests = [
            donor_data.get("hiv"), donor_data.get("hepb"),
            donor_data.get("hepc"), donor_data.get("syphilis"), donor_data.get("malaria")
        ]
        if any(t == "failed" for t in blocked_tests):
            return {
                "eligible": False,
                "status": "BLOCKED",
                "reason": "Failed pathogen screening test",
                "rules_fired": ["PathogenBlock"]
            }
        return {
            "eligible": True,
            "status": "SAFE",
            "reason": "All screening tests passed",
            "rules_fired": ["AllClear"]
        }
    return result

def sort_contracts(contracts: list) -> list:
    """Merge sort contracts by return_deadline ascending."""
    if not contracts:
        return []
    result = call_dsa("sort_contracts", {"contracts": contracts})
    if "error" in result:
        return sorted(contracts, key=lambda c: c.get("return_deadline", "9999"))
    return result.get("sorted_contracts", contracts)

def detect_reaction(pre_vitals: dict, post_vitals: dict) -> dict:
    """Reflex agent: detect transfusion reaction from vitals delta."""
    result = call_dsa("detect_reaction", {
        "pre_vitals": pre_vitals,
        "post_vitals": post_vitals
    })
    if "error" in result:
        # Python reflex agent fallback
        temp_rise = post_vitals.get("temp", 37) - pre_vitals.get("temp", 37)
        bp_drop = pre_vitals.get("bp_sys", 120) - post_vitals.get("bp_sys", 120)
        pulse_rise = post_vitals.get("pulse", 72) - pre_vitals.get("pulse", 72)

        if temp_rise > 2.0 and bp_drop > 30:
            return {"reaction": "HEMOLYTIC", "action": "STOP TRANSFUSION. Call doctor immediately.",
                    "rule": "temp_rise>2 AND bp_drop>30 -> HEMOLYTIC"}
        if bp_drop > 40 or post_vitals.get("o2", 98) < 90:
            return {"reaction": "ANAPHYLAXIS", "action": "CODE BLUE. STOP NOW. Epinephrine 0.3mg IM.",
                    "rule": "bp_drop>40 OR o2<90 -> ANAPHYLAXIS"}
        if temp_rise > 1.5:
            return {"reaction": "FEVER", "action": "Slow infusion rate. Notify attending doctor.",
                    "rule": f"temp_rise={temp_rise:.1f} > 1.5 -> FEVER"}
        return {"reaction": "NORMAL", "action": "Continue transfusion. Monitor every 15 minutes.",
                "rule": "No threshold exceeded -> NORMAL"}
    return result
