# ai_engine.py
"""
LIFELINE v6.0 — OpenRouter AI Engine
Powers: Demand Forecasting, Emergency Triage, Chatbot Assistant, Anomaly Detection
Model: meta-llama/llama-3.3-70b-instruct (free tier on OpenRouter)
"""
from __future__ import annotations

import json
from datetime import datetime

import requests

from lifeline.config import get_settings
from lifeline.privacy import scrub_text

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = get_settings().openrouter_model
FALLBACK_MODELS = [
    "mistralai/mistral-7b-instruct:free",
    "google/gemma-3-27b-it:free",
    "microsoft/phi-3-medium-128k-instruct:free",
    "qwen/qwen3-8b:free",
]

# What the call layer returns instead of an answer. Pages must show these as a problem, never as AI advice.
ERR_NO_KEY = "OpenRouter API key not configured. Add OPENROUTER_API_KEY to your .env file."
ERR_TIMEOUT = "AI request timed out. Please try again."
ERR_BUSY = "All AI models are currently rate-limited. Please wait 1 minute and try again."


def is_error(text: str) -> bool:
    return text in (ERR_NO_KEY, ERR_TIMEOUT, ERR_BUSY)


def _get_api_key() -> str:
    return get_settings().openrouter_api_key.get_secret_value().strip()


def _call_openrouter(system_prompt: str, user_message: str, temperature: float = 0.3) -> str:
    """Core API call with automatic fallback to alternative free models on 429."""
    OPENROUTER_API_KEY = _get_api_key()
    if not OPENROUTER_API_KEY:
        return ERR_NO_KEY

    models_to_try = [DEFAULT_MODEL] + FALLBACK_MODELS

    for model in models_to_try:
        try:
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://lifeline.pk",
                "X-Title": "LIFELINE Blood Logistics",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "temperature": temperature,
                "max_tokens": 1000,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": scrub_text(user_message)},   # last line of defence: CNIC/phone/email
                ],
            }
            resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
            if resp.status_code == 429:
                # Rate limited on this model — try next
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except requests.exceptions.Timeout:
            return ERR_TIMEOUT
        except requests.exceptions.RequestException:
            continue
        except (KeyError, IndexError):
            continue

    return ERR_BUSY


# ─────────────────────────────────────────────
#  AI FEATURE 1: DEMAND FORECASTING ANALYSIS
# ─────────────────────────────────────────────

def ai_demand_forecast(
    hospital_name: str,
    blood_group: str,
    current_stock: int,
    historical_usage: list[float],
    python_forecast: list[float],
    risk_info: dict,
) -> str:
    """
    AI analyses the DSA forecast and adds natural-language insight,
    seasonal context, and procurement recommendations.
    """
    system = """You are LIFELINE's blood supply AI analyst for Lahore hospitals.
You receive blood inventory data and DSA-computed forecasts.
Respond in 3 short sections:
1. Situation Summary (2 sentences)
2. Risk Assessment (1-2 sentences, mention Ramadan/Eid/summer heat if relevant)
3. Action Plan (3 bullet points max, be specific and practical)
Be concise. Use medical logistics language. Always end with a confidence score (Low/Medium/High)."""

    user = f"""Hospital: {hospital_name}
Blood Group: {blood_group}
Current Stock: {current_stock} units
Last 14 days usage: {historical_usage}
7-day Forecast (DSA weighted moving average): {python_forecast}
Risk Level: {risk_info['risk_level']}
Days until stockout: {risk_info['days_until_stockout']}
Recommended reorder quantity: {risk_info['recommended_reorder']} units
Today: {datetime.now().strftime('%A, %d %B %Y')}"""

    return _call_openrouter(system, user, temperature=0.2)


# ─────────────────────────────────────────────
#  AI FEATURE 2: EMERGENCY TRIAGE PRIORITIZATION
# ─────────────────────────────────────────────

def ai_emergency_triage(
    patient_list: list[dict],
    available_stock: dict[str, int],
) -> str:
    """
    AI reads the current emergency queue and available stock,
    then recommends a prioritized fulfillment order with medical reasoning.
    patient_list: list of dicts with name, blood_group, units_needed, condition, priority
    available_stock: dict of blood_group → units available
    """
    system = """You are a critical care AI triage assistant for LIFELINE blood logistics.
Given a list of patients needing blood and available stock, provide:
1. Triage Order — ranked list (1 = most urgent first) with 1-line medical justification per patient
2. Stock Allocation Plan — which patient gets how many units from which blood group
3. Shortage Alert — if stock is insufficient, flag which patients may not be served

Rules:
- Life-threatening conditions always first
- Children and pregnant women get priority in ties
- If blood group unavailable, suggest nearest compatible group
- Be brief. This is a real-time clinical decision tool."""

    patient_json = json.dumps(patient_list, indent=2)
    stock_json = json.dumps(available_stock, indent=2)

    user = f"""Emergency Queue:
{patient_json}

Available Blood Stock:
{stock_json}

Timestamp: {datetime.now().strftime('%H:%M — %d %B %Y')}"""

    return _call_openrouter(system, user, temperature=0.1)


# ─────────────────────────────────────────────
#  AI FEATURE 3: MEDICAL CHATBOT ASSISTANT
# ─────────────────────────────────────────────

def ai_chatbot(
    question: str,
    context: dict,
    chat_history: list[dict] | None = None,
) -> str:
    """
    Conversational AI assistant for doctors and hospital staff.
    context: dict with inventory summary, hospital name, recent alerts, etc.
    chat_history: list of {role, content} dicts for multi-turn conversation
    """
    system = f"""You are LIFELINE Assistant — an intelligent AI helper for {context.get('hospital_name', 'the hospital')} blood bank.

Current Inventory Summary: {json.dumps(context.get('inventory', {}), indent=2)}
Active Alerts: {context.get('alerts', 'None')}
Today: {datetime.now().strftime('%A, %d %B %Y, %H:%M')}

Your role:
- Answer questions about blood inventory, donors, compatibility, and logistics
- Explain blood group compatibility in simple terms
- Help staff find nearby hospitals with required blood types
- Provide guidance on blood storage and handling protocols
- Alert staff to critical shortages proactively

Rules:
- ALWAYS respond in clear English only, regardless of the language used in the question
- Never mix languages or produce garbled text — if unsure, just use simple English
- Keep answers concise and clinically accurate
- If asked about a specific patient, remind staff to verify in the system
- Never fabricate inventory numbers — only use the context provided
- Use Pakistan Standard Time and Pakistani hospital context"""

    messages: list[dict[str, str]] = []
    if chat_history:
        messages.extend({**m, "content": scrub_text(str(m.get("content", "")))} for m in chat_history[-6:])
    messages.append({"role": "user", "content": scrub_text(question)})

    OPENROUTER_API_KEY = _get_api_key()
    if not OPENROUTER_API_KEY:
        return ERR_NO_KEY

    models_to_try = [DEFAULT_MODEL] + FALLBACK_MODELS

    for model in models_to_try:
        try:
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://lifeline.pk",
                "X-Title": "LIFELINE Blood Logistics",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "temperature": 0.4,
                "max_tokens": 600,
                "messages": [{"role": "system", "content": system}] + messages,
            }
            resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
            if resp.status_code == 429:
                continue  # try next model
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception:
            continue

    return ERR_BUSY


# ─────────────────────────────────────────────
#  AI FEATURE 4: ANOMALY DETECTION
# ─────────────────────────────────────────────

def ai_anomaly_detection(
    transfusion_logs: list[dict],
    audit_logs: list[dict],
    inventory_changes: list[dict],
) -> str:
    """
    AI scans recent logs for suspicious patterns:
    - Unusually large blood withdrawals
    - Rapid inventory drops without matching transfusions
    - Off-hours access patterns
    - Same blood group requested repeatedly by same user
    - Expiry manipulation patterns
    """
    system = """You are LIFELINE's security AI — a blood bank anomaly detection system.
Analyse the provided logs for suspicious, irregular, or potentially fraudulent activity.

Output format:
1. Anomalies Detected (list each with severity: LOW / MEDIUM / HIGH / CRITICAL)
   - Description of the anomaly
   - Why it's suspicious
   - Recommended action

2. Normal Patterns (brief confirmation of what looks fine)

3. Summary Risk Score: X/10 (where 10 = extremely suspicious)

Be specific. Reference actual log entries. If nothing is suspicious, say so clearly."""

    transfusion_sample = json.dumps(transfusion_logs[-20:] if len(transfusion_logs) > 20 else transfusion_logs, indent=2)
    audit_sample = json.dumps(audit_logs[-30:] if len(audit_logs) > 30 else audit_logs, indent=2)
    inv_sample = json.dumps(inventory_changes[-15:] if len(inventory_changes) > 15 else inventory_changes, indent=2)

    user = f"""Recent Transfusion Logs (last 20):
{transfusion_sample}

Audit Trail (last 30 events):
{audit_sample}

Inventory Changes (last 15):
{inv_sample}

Analysis Time: {datetime.now().strftime('%H:%M — %d %B %Y')}"""

    return _call_openrouter(system, user, temperature=0.1)


# ─────────────────────────────────────────────
#  AI FEATURE 5: SMART BLOOD EXCHANGE ADVISOR
# ─────────────────────────────────────────────

def ai_exchange_advisor(
    requesting_hospital: str,
    blood_group: str,
    units_needed: int,
    donor_hospitals: list[dict],
    graph_routes: list[dict],
) -> str:
    """
    AI recommends the optimal blood exchange strategy
    combining DSA routing data with contextual reasoning.
    donor_hospitals: list of {name, distance_km, units_available, path}
    """
    system = """You are LIFELINE's blood logistics AI coordinator for Lahore.
Given a blood exchange request and routing options from our DSA graph engine,
recommend the optimal transfer strategy.

Output:
1. Recommended Transfer Plan (hospital, units to request, estimated delivery time)
2. Backup Plan (in case primary falls through)
3. Urgency Assessment (can this wait or is it time-critical?)
4. Coordination Notes (what staff should communicate to the donor hospital)

Assume Lahore traffic: 5 km = ~15 min by ambulance in normal conditions.
Consider: blood viability (max 4 hours for packed RBCs in transit without special equipment)."""

    donor_json = json.dumps(donor_hospitals, indent=2)
    routes_json = json.dumps(graph_routes, indent=2)

    user = f"""Requesting Hospital: {requesting_hospital}
Blood Group Needed: {blood_group}
Units Required: {units_needed}

Available Donor Hospitals (ranked by DSA Dijkstra distance):
{donor_json}

Optimal Routes from DSA Graph:
{routes_json}

Request Time: {datetime.now().strftime('%H:%M — %d %B %Y')}"""

    return _call_openrouter(system, user, temperature=0.2)