"""Admin console: users, hospitals, the audit trail, AI usage and the system self-test."""
from __future__ import annotations

import re

import streamlit as st

from lifeline import selftest
from lifeline.auth.passwords import PasswordPolicyError, validate_password
from lifeline.auth.roles import Role
from lifeline.auth.service import create_user
from lifeline.ui import components as ui
from lifeline.ui.layout import guard, page
from utils.database import get_ai_logs, get_all_hospitals, get_all_users, get_audit_logs, get_blood_summary

user = page(__file__, "Admin", "Users, hospitals, the audit trail and system health")

EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def _stamp(value: object) -> str:
    return str(value or "")[:16].replace("T", " ")


with guard():
    hospitals = get_all_hospitals()
    tab_users, tab_hospitals, tab_audit, tab_ai, tab_health = st.tabs(["Users", "Hospitals", "Audit log", "AI usage", "System self-test"])

    with tab_users:
        users = get_all_users()
        ui.kpi_row(ui.kpi_card("Users", len(users)),
                   *(ui.kpi_card(role.label, sum(1 for u in users if u["role"] == role.value)) for role in Role))
        ui.data_table(
            users,
            [ui.Col("Name", "name"), ui.Col("Email", "email"),
             ui.Col("Role", "role", render=lambda v, r: ui.status_pill(Role(v).label) if v in {x.value for x in Role} else ui.status_pill("unknown")),
             ui.Col("Hospital", "hospital_name", render=lambda v, r: v or "Global"), ui.Col("Created", "created_at", render=lambda v, r: _stamp(v))],
            key="adm_users", page_size=10, empty_title="No users yet", empty_body="Create the first one below.")

        ui.section_header("Add a user")
        c1, c2 = st.columns(2)
        email = c1.text_input("Email", key="nu_email")
        name = c1.text_input("Full name", key="nu_name")
        role = c2.selectbox("Role", [r.value for r in Role], format_func=lambda v: Role(v).label, index=2, key="nu_role")
        by_name = {h["name"]: h["id"] for h in hospitals}
        needs_hospital = Role(role) is not Role.SUPER_ADMIN
        hospital_name = c2.selectbox("Hospital", list(by_name), key="nu_hosp", disabled=not needs_hospital,
                                     help="A super admin belongs to no single hospital." if not needs_hospital else None)
        password = c1.text_input("Password", type="password", key="nu_pw", help="At least 8 characters.")
        problems: dict[str, str] = {}
        if email.strip() and not EMAIL.fullmatch(email.strip()):
            problems["email"] = "That does not look like an email address."
        if password:
            try:
                validate_password(password)
            except PasswordPolicyError as exc:
                problems["password"] = str(exc)
        ui.field_error(problems.get("email"))
        ui.field_error(problems.get("password"))
        if st.button("Create user", type="primary", key="nu_go"):
            if not (email.strip() and name.strip() and password):
                ui.field_error("Email, full name and password are all required.")
            elif not problems:
                ok, message = create_user(email, name, password, role, by_name[hospital_name] if needs_hospital else None, user.id)
                if ok:
                    st.toast(message)
                    st.rerun()
                ui.alert_banner(message, "danger", title="Could not create the user")

    with tab_hospitals:
        network_units = sum(sum(get_blood_summary(h["id"]).values()) for h in hospitals)
        ui.kpi_row(ui.kpi_card("Hospitals", len(hospitals)), ui.kpi_card("Units in the network", network_units),
                   ui.kpi_card("Cities", len({h.get("city") for h in hospitals})))
        ui.data_table(
            hospitals,
            [ui.Col("Hospital", "name"), ui.Col("City", "city"), ui.Col("Address", "address"), ui.Col("Phone", "phone"),
             ui.Col("Stock", "stock_status", render=lambda v, r: ui.status_pill(v or "ok")),
             ui.Col("Coordinates", "latitude", render=lambda v, r: f"{r['latitude']:.4f}, {r['longitude']:.4f}", sortable=False, search=False)],
            key="adm_hosp", page_size=10, empty_title="No hospitals", empty_body="Seed the database or add hospitals.")

    with tab_audit:
        limit = st.slider("Show the last N entries", 10, 200, 50, key="adm_limit")
        ui.data_table(
            get_audit_logs(limit),
            [ui.Col("When", "timestamp", render=lambda v, r: _stamp(v)), ui.Col("Action", "action_type", render=lambda v, r: ui.status_pill(v or "-")),
             ui.Col("Description", "description"), ui.Col("By", "user_name", render=lambda v, r: v or "system")],
            key="adm_audit", page_size=15, empty_title="No audit entries yet", empty_body="Every change is recorded here.")
        st.caption("The audit log is append-only: entries cannot be edited or deleted from the application or the database.")

    with tab_ai:
        ui.data_table(
            get_ai_logs(50),
            [ui.Col("When", "created_at", render=lambda v, r: _stamp(v)), ui.Col("Feature", "feature", render=lambda v, r: ui.status_pill(v or "-")),
             ui.Col("Input", "input_summary"), ui.Col("Response preview", "response_preview", render=lambda v, r: f"{str(v or '')[:70]}…"),
             ui.Col("Hospital", "hospital_id", render=lambda v, r: v if v else "network")],
            key="adm_ai", page_size=10, empty_title="No AI usage yet", empty_body="Answers from the AI Center are logged here.")

    with tab_health:
        ui.section_header("System self-test", "runs every engine operation against a known answer and checks the database")
        if st.button("Run self-test", type="primary", key="st_run"):
            st.session_state["selftest"] = [r.__dict__ for r in selftest.run_all()]
        results = st.session_state.get("selftest")
        if results is None:
            ui.empty_state("Not run yet", "Press the button to check the engine and the database.", icon="○")
        else:
            failed = [r for r in results if not r["ok"]]
            ui.kpi_row(ui.kpi_card("Checks", len(results)), ui.kpi_card("Passed", len(results) - len(failed), tone="success"),
                       ui.kpi_card("Failed", len(failed), tone="danger" if failed else "neutral"))
            if failed:
                ui.alert_banner(f"{len(failed)} check(s) failed. Do not rely on the system until they are fixed.", "danger", title="Self-test failed")
            else:
                ui.alert_banner("Every check passed.", "success", title="Healthy")
            ui.data_table(results, [ui.Col("Area", "area"), ui.Col("Check", "name"),
                                    ui.Col("Result", "ok", render=lambda v, r: ui.status_pill("pass" if v else "fail", kind="success" if v else "danger")),
                                    ui.Col("Time (ms)", "ms", align="right"), ui.Col("Detail", "detail", sortable=False)],
                          key="st_tbl", page_size=20)
