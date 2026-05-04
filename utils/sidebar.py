import streamlit as st
import os
from utils.supabase_client import get_notifications, mark_notifications_read
from utils.helpers import pakistan_time

def render_sidebar():
    if not st.session_state.get("logged_in"):
        return

    role     = st.session_state.get("user_role")
    hosp_id  = st.session_state.get("hospital_id")
    fullname = st.session_state.get("full_name", "User")
    
    with st.sidebar:
        if os.path.exists("logo.png"):
            st.image("logo.png", use_container_width=True)
        else:
            st.markdown("<h2 style='text-align:center; color:#ff416c;'>LIFELINE</h2>", unsafe_allow_html=True)

        st.markdown("<hr style='border-color:rgba(255,65,108,0.2); margin:8px 0;'>", unsafe_allow_html=True)

        initials = fullname[0].upper() if fullname else "U"
        role_label = {"super_admin":"Super Admin","hospital_admin":"Hospital Admin","staff":"Staff"}.get(role, role)
        role_badge_class = {"super_admin":"badge-critical","hospital_admin":"badge-info","staff":"badge-caution"}.get(role,"badge-info")
        st.markdown(f"""
        <div style='display:flex; align-items:center; gap:10px; padding:10px 0;'>
            <div style='width:38px;height:38px;border-radius:50%;background:linear-gradient(135deg,#ff416c,#ff4b2b);
                        display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1rem;
                        color:white;flex-shrink:0;'>{initials}</div>
            <div>
                <div style='color:white;font-weight:600;font-size:0.9rem;'>{fullname}</div>
                <span class='badge {role_badge_class}'>{role_label}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        clock_slot = st.empty()
        clock_slot.markdown(f"""<div style='text-align:center; font-size:0.8rem; color:#95A5A6;
            background:rgba(0,0,0,0.3); border-radius:8px; padding:6px; margin:6px 0;'>
            {pakistan_time()}</div>""", unsafe_allow_html=True)

        notifs = get_notifications(hosp_id, unread_only=True)
        n_count = len(notifs)
        with st.expander(f"Notifications ({n_count})"):
            if notifs:
                for n in notifs[:5]:
                    c = "#ff416c" if n["type"] == "critical" else ("#FFB347" if n["type"] == "warning" else "#3498DB")
                    st.markdown(f"<div style='border-left:3px solid {c}; padding-left:8px; margin-bottom:8px;'>"
                                f"<div style='font-size:0.8rem; font-weight:600; color:white;'>{n['title']}</div>"
                                f"<div style='font-size:0.7rem; color:#95A5A6;'>{n['message']}</div>"
                                f"</div>", unsafe_allow_html=True)
                if st.button("Mark All Read", key="read_notifs_sb"):
                    mark_notifications_read(hosp_id)
                    st.rerun()
            else:
                st.markdown("<div style='font-size:0.8rem; color:#95A5A6;'>No new notifications</div>", unsafe_allow_html=True)

        st.markdown("<hr style='border-color:rgba(255,255,255,0.06); margin:8px 0;'>", unsafe_allow_html=True)
        st.markdown("<div class='section-header'>NAVIGATION</div>", unsafe_allow_html=True)

        st.markdown("""
        <style>
        [data-testid="stPageLink-NavLink"] {
            border-radius: 6px;
            margin-bottom: 4px;
            font-size: 0.95rem;
            transition: all 0.2s;
            font-weight: 500;
        }
        [data-testid="stPageLink-NavLink"]:hover {
            background: rgba(255,65,108,0.15) !important;
        }
        [data-testid="stPageLink-NavLink"] p {
            color: #ECF0F1 !important;
        }
        [data-testid="stPageLink-NavLink"]:hover p {
            color: #ff416c !important;
        }
        /* Hide page icons globally in the custom sidebar */
        [data-testid="stPageLink-Icon"] { display: none !important; }
        [data-testid="stPageLink-NavLink"] span:first-child:not([class]) { display: none !important; }
        </style>
        """, unsafe_allow_html=True)
        
        st.page_link("app.py", label="Home")
        st.page_link("pages/1_dashboard.py", label="Dashboard")
        st.page_link("pages/2_inventory.py", label="Inventory")
        st.page_link("pages/3_emergency.py", label="Emergency")
        st.page_link("pages/4_exchange.py", label="Exchange")
        st.page_link("pages/5_screening.py", label="Screening")
        st.page_link("pages/6_contracts.py", label="Contracts")
        st.page_link("pages/7_transfusion.py", label="Transfusion")
        st.page_link("pages/8_analytics.py", label="Analytics")
        
        if role == "super_admin":
            st.page_link("pages/9_admin.py", label="Admin")

        st.markdown("<hr style='border-color:rgba(255,255,255,0.06); margin:8px 0;'>", unsafe_allow_html=True)

        st.markdown("""<div style='text-align:center;'>
            <span class='live-dot'></span>
            <span style='color:#00D2AA; font-size:0.82rem; font-weight:600;'>4 / 4 Hospitals Online</span>
        </div>""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("LOGOUT", use_container_width=True):
            st.session_state.clear()
            st.rerun()
