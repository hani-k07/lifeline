import streamlit as st
import time

from utils.supabase_client import (
    get_exchange_offers, create_exchange_offer, get_hospitals,
    update_exchange_offer, create_contract, add_audit_log
)
from utils.dsa_bridge import find_exchange_match
from utils.helpers import format_countdown

if not st.session_state.get("logged_in"):
    st.warning("Please login from the main page.")
    st.stop()

# Access Control
role = st.session_state.get("user_role", "staff")
if role not in ["super_admin", "hospital_admin"]:
    st.markdown("""
    <style>
    .glass-card {
        background: rgba(20,20,35,0.7);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 16px;
        text-align: center;
    }
    </style>
    <div class='glass-card' style='border-color:rgba(255,65,108,0.4);'>
        <h2 style='color:white;'>🚫 Access Denied</h2>
        <p style='color:#95A5A6;'>You do not have permission to view this page. Hospital Admin or Super Admin only.</p>
    </div>
    """, unsafe_allow_html=True)
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
.stTextInput>div>div>input,.stSelectbox>div>div>div,.stNumberInput>div>div>input{background:rgba(0,0,0,0.3)!important;border:1px solid rgba(255,255,255,0.1)!important;color:white!important;border-radius:10px!important;}
.stButton>button{background:linear-gradient(135deg,#ff416c,#ff4b2b)!important;color:white!important;border:none!important;border-radius:10px!important;font-weight:600!important;transition:all 0.3s ease!important;box-shadow:0 4px 15px rgba(255,65,108,0.3)!important;}
.stButton>button:hover{transform:translateY(-2px)!important;box-shadow:0 8px 25px rgba(255,65,108,0.5)!important;}
.data-table{width:100%;border-collapse:collapse;}
.data-table th{background:rgba(255,65,108,0.1);color:#ff416c;font-size:0.68rem;text-transform:uppercase;letter-spacing:1px;padding:10px 14px;text-align:left;border-bottom:1px solid rgba(255,65,108,0.2);}
.data-table td{padding:10px 14px;color:#ECF0F1;font-size:0.85rem;border-bottom:1px solid rgba(255,255,255,0.03);}
</style>""", unsafe_allow_html=True)

st.markdown("<h1 style='color:white;'><span style='color:#3498DB;'>🔄</span> Blood Exchange Marketplace</h1>", unsafe_allow_html=True)

st.markdown("""<div class='glass-card'>
    <p style='color:#95A5A6;font-size:1.1rem;margin:0;'>If your hospital has surplus <b style='color:#2ECC71;'>B+</b> but needs <b style='color:#3498DB;'>A+</b>, and another hospital has surplus <b style='color:#3498DB;'>A+</b> but needs <b style='color:#2ECC71;'>B+</b>, LIFELINE matches you instantly for zero-cost exchange.</p>
</div>""", unsafe_allow_html=True)

# ── POST OFFER FORM ─────────────────────────────
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>POST EXCHANGE OFFER</div>", unsafe_allow_html=True)

with st.form("offer_form"):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<h4 style='color:#00D2AA;'>🟢 WE HAVE (Surplus)</h4>", unsafe_allow_html=True)
        has_bg = st.selectbox("Blood Group", ["A+","A-","B+","B-","O+","O-","AB+","AB-"], key="has_bg")
        has_units = st.number_input("Units Available", 1, 10, 1, key="has_units")
    with c2:
        st.markdown("<h4 style='color:#ff416c;'>🔴 WE NEED (Deficit)</h4>", unsafe_allow_html=True)
        needs_bg = st.selectbox("Blood Group", ["A+","A-","B+","B-","O+","O-","AB+","AB-"], key="needs_bg")
        needs_units = st.number_input("Units Required", 1, 10, 1, key="needs_units")
    
    st.markdown("<br>", unsafe_allow_html=True)
    submitted = st.form_submit_button("FIND MATCH 🔄", use_container_width=True)

if submitted:
    if has_bg == needs_bg:
        st.error("Cannot exchange same blood group.")
    elif not hosp_id:
        st.error("Please login as a hospital to post offers.")
    else:
        new_offer = {
            "offering_hospital_id": hosp_id,
            "has_blood_group": has_bg,
            "needs_blood_group": needs_bg,
            "units": has_units
        }
        
        all_pending = get_exchange_offers(status="pending")
        # Filter out own offers
        others_pending = [o for o in all_pending if o.get("offering_hospital_id") != hosp_id]
        
        with st.spinner("Searching Network HashMap for Complementary Offer..."):
            match_res = find_exchange_match(new_offer, others_pending)
            time.sleep(1)
            
            if match_res.get("matched"):
                matched_offer = match_res.get("matched_offer", {})
                partner_id = matched_offer.get("offering_hospital_id")
                
                # Save new offer as matched
                o_id = create_exchange_offer({
                    "offering_hospital_id": hosp_id,
                    "receiving_hospital_id": partner_id,
                    "offered_blood_group": has_bg,
                    "requested_blood_group": needs_bg,
                    "units": has_units,
                    "status": "matched"
                })
                # Update existing
                update_exchange_offer(matched_offer.get("id"), "matched", hosp_id)
                
                # Create bilateral contracts
                create_contract({
                    "lending_hospital_id": hosp_id, "borrowing_hospital_id": partner_id,
                    "blood_group": has_bg, "units": has_units, "is_exchange": 1
                })
                create_contract({
                    "lending_hospital_id": partner_id, "borrowing_hospital_id": hosp_id,
                    "blood_group": needs_bg, "units": needs_units, "is_exchange": 1
                })
                
                add_audit_log("EXCHANGE_MATCHED", st.session_state["email"], hosp_id, "exchange", o_id, {"partner": partner_id})
                
                st.success("✓ PERFECT MATCH FOUND! Bilateral transfer contracts generated.")
                st.balloons()
            else:
                o_id = create_exchange_offer({
                    "offering_hospital_id": hosp_id,
                    "offered_blood_group": has_bg,
                    "requested_blood_group": needs_bg,
                    "units": has_units,
                    "status": "pending"
                })
                add_audit_log("EXCHANGE_POSTED", st.session_state["email"], hosp_id, "exchange", o_id, new_offer)
                st.info("Offer posted to marketplace. Awaiting network match.")

st.markdown("</div>", unsafe_allow_html=True)
st.markdown("<p style='color:#95A5A6;font-size:0.75rem;'>DSA NOTE: HashMap O(1) matching instantly checks for complementary A/B needs across the active network pool.</p>", unsafe_allow_html=True)

# ── MARKETPLACE BOARD ───────────────────────────
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
t1, t2 = st.tabs(["Pending Offers", "Active Matches"])

with t1:
    pending = get_exchange_offers(status="pending")
    if pending:
        rows = ""
        for p in pending:
            rows += f"""<tr>
                <td>{p.get('offer_code')}</td>
                <td>{p.get('offering_name','Unknown')}</td>
                <td><span style='color:#00D2AA;font-weight:bold;'>{p.get('offered_blood_group')}</span> ({p.get('units')}u)</td>
                <td><span style='color:#ff416c;font-weight:bold;'>{p.get('requested_blood_group')}</span></td>
                <td><button style='background:transparent;border:1px solid #3498DB;color:#3498DB;border-radius:4px;'>Accept</button></td>
            </tr>"""
        st.markdown(f"<table class='data-table'><thead><tr><th>Offer ID</th><th>Hospital</th><th>Offering</th><th>Requesting</th><th>Action</th></tr></thead><tbody>{rows}</tbody></table>", unsafe_allow_html=True)
    else:
        st.info("No pending offers.")

with t2:
    matched = get_exchange_offers(status="matched")
    if matched:
        for m in matched:
            st.markdown(f"""<div style='background:rgba(0,0,0,0.3);border-left:3px solid #00D2AA;padding:15px;margin-bottom:10px;border-radius:8px;'>
                <div style='display:flex;justify-content:space-between;align-items:center;'>
                    <div>
                        <b style='color:white;font-size:1.1rem;'>{m.get('offering_name')} ↔ {m.get('receiving_name')}</b><br>
                        <span style='color:#95A5A6;font-size:0.85rem;'>Exchanging <b>{m.get('offered_blood_group')}</b> for <b>{m.get('requested_blood_group')}</b> ({m.get('units')} units)</span>
                    </div>
                    <span class='badge badge-safe'>MATCHED ✓</span>
                </div>
            </div>""", unsafe_allow_html=True)
    else:
        st.info("No active matches.")

st.markdown("</div>", unsafe_allow_html=True)
