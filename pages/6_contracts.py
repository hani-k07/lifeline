import streamlit as st
import time

from utils.supabase_client import (
    get_active_contracts, mark_contract_returned, add_audit_log,
    get_hospital_by_id, get_patient_by_id, get_blood_units
)
from utils.dsa_bridge import sort_contracts
from utils.pdf_generator import generate_contract
from utils.helpers import format_countdown

if not st.session_state.get("logged_in"):
    st.warning("Please login from the main page.")
    st.stop()

import datetime
from utils.sidebar import render_sidebar
render_sidebar()

def get_contract_time_status(end_date_str):
    """
    Given an end_date string (ISO format), return:
      - days_remaining (int)
      - status_label (str): "EXPIRED", "CRITICAL", "WARNING", "OK"
      - color (str): hex color for display
    """
    try:
        end_date = datetime.datetime.fromisoformat(end_date_str)
    except:
        return None, "UNKNOWN", "#95A5A6"
    
    now  = datetime.datetime.now()
    diff = end_date - now
    days = diff.days
    
    if days < 0:
        return days, "EXPIRED",  "#E74C3C"
    elif days <= 1:
        return days, "CRITICAL", "#E74C3C"
    elif days <= 3:
        return days, "WARNING",  "#F39C12"
    else:
        return days, "OK",       "#00D2AA"

role    = st.session_state.get("user_role")
hosp_id = st.session_state.get("hospital_id") if role != "super_admin" else None

from utils.styles import get_glass_css
st.markdown(get_glass_css(), unsafe_allow_html=True)

st.markdown("<h1 style='color:white;'><span style='color:#9B59B6;'>📄</span> Contract Management</h1>", unsafe_allow_html=True)

all_contracts = get_active_contracts()
if hosp_id:
    contracts = [c for c in all_contracts if c.get("lending_hospital_id")==hosp_id or c.get("borrowing_hospital_id")==hosp_id]
else:
    contracts = all_contracts

# ── BREACH BANNER ───────────────────────────────
breaches = [c for c in contracts if c.get("hours_remaining", 99) < 2]
if breaches:
    for b in breaches:
        contact = "Unknown"
        # If we are lending, show borrowing contact
        if hosp_id and b.get("lending_hospital_id") == hosp_id:
            bh = get_hospital_by_id(b.get("borrowing_hospital_id"))
            contact = bh.get("contact_number") if bh else "Unknown"
        st.markdown(f"""<div class='alert-critical' style='animation:pulse-red 2s infinite;'>
            <h3 style='margin:0;color:#ff416c;'>🚨 URGENT: CONTRACT BREACH IMMINENT</h3>
            <p style='margin:5px 0 0 0;'>Ticket <b>{b.get('ticket_id')}</b> must be returned in {format_countdown(b.get('seconds_remaining',0))}. Contact partner hospital at: <b>{contact}</b></p>
        </div>""", unsafe_allow_html=True)

# ── ACTIVE CONTRACTS ────────────────────────────
st.markdown("<div class='section-header'>ACTIVE TRANSFERS & EXCHANGES</div>", unsafe_allow_html=True)

sorted_c = sort_contracts(contracts)

if sorted_c:
    # Use st.empty to update countdown once (Streamlit looping restricts real-time updates without rerun)
    container = st.empty()
    
    # We render the contracts once. For a real live ticking clock, we would use a while loop with time.sleep(1),
    # but in Streamlit this blocks other interactions. We render once per interaction.
    html = ""
    for c in sorted_c:
        tid = c.get("ticket_id")
        hrs = c.get("hours_remaining", 99)
        secs= c.get("seconds_remaining", 0)
        deadline = c.get("return_deadline", "")
        
        # New Status Badge Logic
        days_rem, status_lbl, status_color = get_contract_time_status(deadline)
        if days_rem is not None:
            if days_rem < 0:
                badge_label = f"⛔ Expired {abs(days_rem)} days ago"
            elif days_rem == 0:
                badge_label = "⚠️ Expires TODAY"
            else:
                badge_label = f"⏳ {days_rem} days remaining"
            
            status_map = {"EXPIRED": "231,76,60", "CRITICAL": "231,76,60", "WARNING": "243,156,18", "OK": "0,210,170"}
            rgb = status_map.get(status_lbl, "149,165,166")
            badge_html = f"""
            <div style='
                background:rgba({rgb},0.15);
                border:1px solid {status_color};
                border-radius:8px;
                padding:4px 10px;
                display:inline-block;
                color:{status_color};
                font-size:0.75rem;
                font-weight:600;
                margin-top:8px;
            '>{badge_label}</div>
            """
        else:
            badge_html = ""

        border = "#ff416c" if hrs < 6 else ("#FFB347" if hrs < 12 else "#00D2AA")
        cd_cls = "countdown-red" if hrs < 6 else ("countdown-amber" if hrs < 12 else "countdown-green")
        prog   = max(0, min(100, ((24 - hrs) / 24) * 100))
        
        html += f"""<div class='glass-card' style='border-left:4px solid {border};padding:15px;margin-bottom:15px;'>
            <div style='display:flex;justify-content:space-between;align-items:center;'>
                <div style='flex:1;'>
                    <code style='color:white;font-size:1.2rem;background:rgba(255,255,255,0.1);padding:4px 8px;border-radius:4px;'>{tid}</code>
                    <span style='margin-left:15px;color:#95A5A6;'>{c.get('lending_hospital_name')} ➔ {c.get('borrowing_hospital_name')}</span>
                    <br>{badge_html}
                </div>
                <div style='flex:1;text-align:center;'>
                    <b style='color:white;font-size:1.1rem;'>{c.get('blood_group')} {c.get('component')}</b> ({c.get('units')} Units)
                </div>
                <div style='flex:1;text-align:right;'>
                    <div class='countdown {cd_cls}'>{format_countdown(secs)}</div>
                    <div style='font-size:0.7rem;color:#95A5A6;'>remaining</div>
                </div>
            </div>
            <div style='margin-top:15px;background:rgba(0,0,0,0.4);border-radius:4px;height:6px;overflow:hidden;'>
                <div style='width:{prog}%;background:{border};height:100%;transition:width 1s;'></div>
            </div>
        </div>"""
    container.markdown(html, unsafe_allow_html=True)
    
    # Action buttons per contract
    for c in sorted_c:
        tid = c.get("ticket_id")
        col1, col2, col3 = st.columns([2, 2, 6])
        with col1:
            if st.button(f"Mark Returned ✓", key=f"ret_{tid}", use_container_width=True):
                mark_contract_returned(tid)
                add_audit_log("CONTRACT_RETURNED", st.session_state["email"], hosp_id, "contract", tid, {"status":"returned"})
                st.success(f"Contract {tid} closed.")
                time.sleep(1)
                st.rerun()
        with col2:
            # Generate PDF data
            # In a real app we'd fetch full details, here we mock some for the PDF
            pdf_data = {
                "ticket_id": tid, "status": c.get("status"),
                "lending_hospital_name": c.get("lending_hospital_name"),
                "borrowing_hospital_name": c.get("borrowing_hospital_name"),
                "blood_group": c.get("blood_group"), "component": c.get("component"),
                "units": c.get("units"), "issue_time": c.get("issue_time"),
                "return_deadline": c.get("return_deadline"), "is_exchange": c.get("is_exchange")
            }
            pdf_bytes = generate_contract(pdf_data)
            st.download_button("Download PDF ⬇", data=pdf_bytes, file_name=f"{tid}.pdf", mime="application/pdf", key=f"pdf_{tid}", use_container_width=True)
        st.markdown("<hr style='border-color:rgba(255,255,255,0.05);'>", unsafe_allow_html=True)
else:
    st.info("No active contracts.")
