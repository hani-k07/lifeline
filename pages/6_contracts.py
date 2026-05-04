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

from utils.sidebar import render_sidebar
render_sidebar()


role    = st.session_state.get("user_role")
hosp_id = st.session_state.get("hospital_id") if role != "super_admin" else None

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
html,body,[class*="css"]{font-family:'Outfit',sans-serif!important;}
.stApp{background:linear-gradient(-45deg,#0f0c29,#302b63,#24243e,#1a1a2e);background-size:400% 400%;animation:gradientBG 15s ease infinite;}
@keyframes gradientBG{0%{background-position:0% 50%;}50%{background-position:100% 50%;}100%{background-position:0% 50%;}}
footer,#MainMenu{visibility:hidden;} [data-testid='stSidebarNav'] { display: none !important; } [data-testid='stHeader'] { background: transparent !important; } [data-testid='stHeaderActionElements'] { display: none !important; }
.block-container{padding-top:1.5rem!important;}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0D0D1A 0%,#1C1C2E 100%)!important;border-right:1px solid rgba(255,65,108,0.2);}
[data-testid="stSidebar"] *{color:#ECF0F1!important;}
.glass-card{background:rgba(20,20,35,0.7);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:24px;margin-bottom:16px;box-shadow:0 8px 32px rgba(0,0,0,0.4);transition:all 0.3s ease;}
.section-header{font-size:0.68rem;font-weight:600;color:#ff416c;text-transform:uppercase;letter-spacing:2px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid rgba(255,65,108,0.2);}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:0.7rem;font-weight:600;}
.countdown{font-family:'Courier New',monospace;font-size:1.6rem;font-weight:700;letter-spacing:3px;}
.countdown-red{color:#ff416c;text-shadow:0 0 10px rgba(255,65,108,0.5);}
.countdown-amber{color:#FFB347;text-shadow:0 0 10px rgba(255,179,71,0.5);}
.countdown-green{color:#00D2AA;text-shadow:0 0 10px rgba(0,210,170,0.5);}
.alert-critical{background:linear-gradient(90deg,rgba(255,65,108,0.15),transparent);border-left:3px solid #ff416c;border-radius:0 8px 8px 0;padding:15px;margin-bottom:16px;color:#ECF0F1;}
.stButton>button{background:linear-gradient(135deg,#ff416c,#ff4b2b)!important;color:white!important;border:none!important;border-radius:8px!important;font-weight:600!important;transition:all 0.3s ease!important;padding:4px 12px!important;}
.stButton>button:hover{transform:translateY(-2px)!important;box-shadow:0 4px 15px rgba(255,65,108,0.5)!important;}
.stProgress>div>div{background:linear-gradient(90deg,#ff416c,#ff4b2b)!important;}
</style>""", unsafe_allow_html=True)

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
        
        border = "#ff416c" if hrs < 6 else ("#FFB347" if hrs < 12 else "#00D2AA")
        cd_cls = "countdown-red" if hrs < 6 else ("countdown-amber" if hrs < 12 else "countdown-green")
        prog   = max(0, min(100, ((24 - hrs) / 24) * 100))
        
        html += f"""<div class='glass-card' style='border-left:4px solid {border};padding:15px;margin-bottom:15px;'>
            <div style='display:flex;justify-content:space-between;align-items:center;'>
                <div style='flex:1;'>
                    <code style='color:white;font-size:1.2rem;background:rgba(255,255,255,0.1);padding:4px 8px;border-radius:4px;'>{tid}</code>
                    <span style='margin-left:15px;color:#95A5A6;'>{c.get('lending_hospital_name')} ➔ {c.get('borrowing_hospital_name')}</span>
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

# ── DSA NOTE ────────────────────────────────────
st.markdown("""<div class='glass-card' style='background:rgba(52,152,219,0.1);border-color:rgba(52,152,219,0.3);'>
    <h4 style='color:#3498DB;margin-top:0;'>🧠 DSA Engine: Contract Management</h4>
    <ul style='color:#ECF0F1;font-size:0.9rem;margin-bottom:0;'>
        <li><b>Merge Sort:</b> <code style='color:#FFB347;'>O(n log n)</code> guaranteed performance for sorting thousands of contracts by deadline.</li>
        <li><b>HashMap:</b> <code style='color:#FFB347;'>O(1)</code> ticket ID lookup for O(1) status updates.</li>
        <li><b>Min-Heap:</b> <code style='color:#FFB347;'>O(log n)</code> to constantly monitor the nearest breaching contract for alert banners.</li>
    </ul>
</div>""", unsafe_allow_html=True)
