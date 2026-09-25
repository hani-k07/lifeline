# LIFELINE — Phase 0 Audit

**Date:** 2026-09-25 · **Scope:** every tracked and untracked source file, docs, seed/setup scripts, the checked-in `lifeline.db`
**Code changes made:** none. `AUDIT.md` is the only file written. `.env` and `lifeline.db` were verified unmodified afterwards (mtimes unchanged).
**Method:** full read of all `.py`/`.md`/`.bat`/`.txt` files, plus runtime probes run against *scratch copies* of the project (never the repo): engine probes, a 64-pair compatibility check, `setup_database.py` on a fresh directory, and a Streamlit `AppTest` load of all 10 pages × 3 roles against both the old checked-in DB and a freshly seeded one.

---

## 1. Bottom line

The app **starts and every page renders** against the checked-in `lifeline.db`. But:

- It only works because that DB file was built by an *older* `setup_database.py`. **A fresh `setup_database.py` (what `run.bat` runs) produces a DB where super-admin and hospital-admin users get an empty sidebar and cannot use the Admin page or resolve emergencies** (role names disagree, §3-P0-1).
- **Four clinical-safety defects exist in shipped code paths**, none of which are on your list: donor screening never returns DEFER for vitals, the transfusion-reaction monitor reports NORMAL for SpO₂ 84 %, expired stock is counted as available, and inventory consumption silently clamps to zero (§3-P0-2…5).
- Most of the "13 algorithms" in the docs are **not called by any page**. The UI uses ~6 (Dijkstra, TriageQueue, compatibility map, WMA forecast, `screen_donor`, `risk_score`, plus `transfusion_monitor` from a second copy of the engine).
- **All v6 work is uncommitted/untracked** (48 entries in `git status`; `HEAD` is the v5 Supabase app). There is no backup of the working version. → §9 Q1.

What is genuinely good: all SQL is parameterised (no f-string SQL anywhere), the ABO/Rh compatibility table is correct (64/64 pairs verified against an independent rule), `.env` is ignored and has never been in git history, and the algorithm implementations that do exist are readable.

---

## 2. What the project actually is today (ground truth)

| Layer | Reality |
|---|---|
| UI | Streamlit multipage: `app.py` (login) + `pages/1…10`. ~590-line CSS string in `utils/styles.py`, injected per page. |
| Data | SQLite `lifeline.db` via `utils/database.py` (403 lines, one function per query, a new connection per call). 13 tables, **0 indexes**, **only 1 CHECK constraint** (users.role). |
| Auth | `utils/auth.py`: unsalted SHA-256 compare. Session = `st.session_state["logged_in"]`. |
| Algorithms | Two engines: root `dsa_engine.py` (471 lines; graph, triage heap, compat, WMA forecast, screening, risk, transfusion) **is what pages import**. `utils/dsa_engine.py` (979 lines; 13 ops + `run_engine`) is imported only by page 7 (`transfusion_monitor`) and `utils/helpers.py` (itself only used by the broken `test_connection.py`). |
| AI | Root `ai_engine.py`: raw `requests.post` to OpenRouter, 5 features, free-model fallback list. `utils/ai_engine.py` (rule-based strategy classes) is unused. |
| Version label | app.py / run.bat / setup_database.py / sidebar say **v6.0 SQLite**. README says **v5.0 Supabase**. Old PROJECT_REPORT says **C++ `.exe`**. |

Environment on this machine: Python 3.14.4, streamlit 1.57.0, pytest 8.3.2. **`ruff`, `mypy`, `pytest-cov` are not installed**, so lint/type/coverage status is *unverified* (baseline `python -m compileall` passes for all app files).

---

## 3. Verification of your items 1–17

Legend: ✅ confirmed · ⚠️ partly true / needs correction · ❌ not as stated

| # | Your claim | Verdict | Evidence |
|---|---|---|---|
| 1 | `.env` has a real OpenRouter key | ✅ | `.env` has a 73-char `sk-or-…` key. **Not** tracked (`.gitignore:2-3`) and **never in any of the 5 commits** (searched all revs). Code never prints/logs it (`ai_engine.py:25-28` reads it only). Still: **rotate it** — it is plaintext on disk and this session's tooling read the folder. |
| 2 | Unsalted SHA-256; plaintext password column in seed | ✅ | `utils/auth.py:7-8,17`, `setup_database.py:17-18`, `pages/10_admin.py:97`. All 11 seeded users share **one** hash (1 distinct value in 11 rows). Plaintext `"password"` key: `seed_data.py:40-44` — but that file is dead Supabase code (§6). `pages/10_admin.py:84` **pre-fills the new-user password field with `lifeline123`**. |
| 3 | Demo creds public; no timeout / rate limit / per-page role checks | ✅ | Creds table always rendered: `app.py:79-89`. No timeout, attempt counter or LOGIN/LOGOUT audit anywhere (grep empty). Role checks exist only on pages 9 (`:38`) and 10 (`:32`) and use the wrong vocabulary (P0-1). Pages 1-8 only check `logged_in`. |
| 4 | CNIC unmasked; PII sent to LLM | ✅ | CNIC rendered raw: `pages/5_screening.py:75`. To LLM: patient **names + conditions** (`9_ai_center.py:136-141`), full transfusion rows incl. `patient_name`/`performed_by` (`:228-231`; `get_transfusions` returns `t.*`), audit rows whose descriptions embed patient names + user names (`:229`), and free-text chat. Prompt/response previews are also stored in `ai_logs`. |
| 5 | Docs contradict each other | ✅ | README = v5/Supabase (`README.md:3-10`, demo creds `:58-65` incl. `staff@lifeline.com` which does not exist in the DB); `PROJECT_REPORT.md` ×2 (root and `docs/`, **different content**) = C++ `.exe`; `DSA_ENGINE_DOCUMENTATION.md` says "~1600 lines" (`:296`; actual 979) and "Production Ready" (`:8`); `docs/DSA_MAPPING.md` maps to C++ ops that no longer exist. `.env.example` still lists Supabase vars and omits `OPENROUTER_API_KEY`. |
| 6 | (decision) SQLite default, optional Supabase, pure Python | — | Accepted. Note the working tree is already SQLite-only; Supabase survives only in dead files (`seed_data.py`, `test_connection.py`, `extras/*`, `.env.example`, README). |
| 7 | `seed_data.py` uses string IDs, `app.py` uses `int(user["id"])` | ✅ | `seed_data.py:26-31,40-45` (`"h-mayo"`, `"u-admin"`). `setup_database.py` is the only seeder that matches the app (INTEGER ids). `seed_data.py` and `test_connection.py` both crash on run (`KeyError: 'SUPABASE_URL'`, `No module named utils.supabase_client`) — verified. |
| 8 | requirements missing supabase/folium/streamlit-folium/bcrypt, no upper bounds | ⚠️ | **Supabase and folium are not needed**: nothing imports `folium`/`streamlit_folium`, and Supabase is dead code. **bcrypt is genuinely missing** (needed for #2). Also missing/unused: `matplotlib` (lazy import in `styles.py:556`, never called), while `openpyxl`, `python-dateutil` are listed but unused, and `reportlab` is only used by an unwired module. No upper bounds ✅. |
| 9 | `antigravity.py` line 1 is a stray `n` = SyntaxError | ⚠️ | Stray `n` is at `antigravity.py:1`, but it is a **NameError at import**, not SyntaxError (`compileall` passes). File is imported by nothing. |
| 10 | `dsa_engine.py` has no `run_engine` and is missing 9 ops | ⚠️ | True of the **root** `dsa_engine.py` (which pages use). **All 13 ops + `run_engine` already exist in `utils/dsa_engine.py`** (`:948-979`) with docstrings/complexity/PEAS — but under a different data contract (string IDs, `status`, `collection_date`, `return_deadline`, `edges` lists) that **does not match the SQLite schema**, so they return garbage on real rows (probe: `fefo_sort` → `available_units: 0`; `predict_shortage` → all CRITICAL/0; `merge_sort` → 0/0). No page calls them. Quality issues inside them are in §5. |
| 11 | HospitalGraph is a full mesh | ✅ | `dsa_engine.py:40-51,287-296`. Probe: 8 nodes → 7 edges/node; every shortest path from node 1 has length ≤ 2 (always the direct edge). BFS has no depth to explore. |
| 12 | Exact-group-only matching; Dijkstra re-run per hospital | ✅ | `dsa_engine.py:102` (`== blood_group`). Probe: A+ request with O- stocked at Services and A+ at Jinnah → only Jinnah returned. Dijkstra runs once at `:99` (result unused) and again per candidate in `:109`. |
| 13 | risk_score double-penalises; screen_donor stops at first rule; missing rules | ✅ **+ worse** | Double penalty: `dsa_engine.py:392-395`, `utils/dsa_engine.py:369-372` (probe: HIV via disease string + flag → two −100 penalties). Stops at first serology hit (`:362`/`:494`). **Bigger bug:** the `All_Clear` rule (`check: lambda: True`) always fires last and overwrites `decision` with `SAFE` (`dsa_engine.py:343-345,352-361`; `utils/dsa_engine.py:475-477,484-493`) → **Hb 9 g/dL, weight 40 kg, SBP 200, fever 38.5 °C, pulse 130 all return `SAFE`** (probes). Only serology rules (priority ≤ 5) ever produce a non-SAFE result. Age and last-donation-gap rules are absent from `screen_donor` in both copies; pulse/temperature rules exist only in the `utils` copy (and are overwritten). |
| 14 | ai_engine duplicates client, timeout skips fallbacks, errors look like answers | ✅ | Duplicate client: `ai_engine.py:31-70` vs `:190-219`. Timeout returns immediately: `:63-64`. Errors are plain strings passed to `render_ai_response` and stored in `ai_logs` as if they were AI output (`9_ai_center.py:102,146,197`). Also: `load_dotenv(override=True)` on **every call** (`:14,27`; overrides real env vars), `OPENROUTER_MODEL` from `.env` is ignored (`:17` hard-codes), fallback model IDs are unverified, no retry/backoff, no cache, no rate limit, `HTTP-Referer` points to a domain you may not own. |
| 15 | utils/pages/setup/test "may be incomplete" | ✅ | See §4 inventory. Missing entirely: tests, `.streamlit/config.toml`, Dockerfile, Makefile, CI, migrations, `ARCHITECTURE.md`, `CHANGELOG.md`. |
| 16 | AI clinical output must be advisory | ⚠️ | Good: nothing AI-generated is auto-applied. Missing: no "verify clinically" label anywhere; AI output is written to `ai_logs` (200-char preview, `database.py:39-47`) **not** the audit trail; the triage prompt lets the LLM choose "nearest compatible group" itself (`ai_engine.py:133`) instead of using the deterministic table; output rendered as unescaped HTML (§5-N7). |
| 17 | Compat/thresholds must be unit-tested against a reference | ✅ | **Zero tests exist.** I ran the check anyway: compat table = correct 64/64 (P0 risk **not** present). Reaction thresholds and screening cut-offs **fail** (§3-P0-2,3). |

---

## 4. File inventory

**Status:** ✅ used & works · ⚠️ used but defective · 🗑 dead/broken · 📄 doc

| File | Lines | Status | Notes |
|---|---:|---|---|
| `app.py` | 89 | ⚠️ | Login gate. Sets session (`:59-70`). No audit, rate limit, timeout; creds shown (`:79-89`). |
| `pages/1_dashboard.py` | 173 | ⚠️ | Hard-coded fake numbers/alerts (`:67,85,171,172`); 1+N queries; role `"admin"` (`:44`). |
| `pages/2_inventory.py` | 177 | ⚠️ | Success banner immediately wiped by `st.rerun()` (`:143-145`); ignores `update_blood_units` result (`:165`). |
| `pages/3_emergency.py` | 184 | ⚠️ | Wrong role strings (`:47,77,119`); unescaped patient name in HTML (`:72`); request does **not** reserve stock; resolving does not touch inventory. |
| `pages/4_exchange.py` | 129 | ⚠️ | Creates `PENDING` exchange rows only; **nothing ever completes/approves them**; inventory never moves; `exchange_match` not used. |
| `pages/5_screening.py` | 185 | ⚠️ | Age input clamped 18-65 (`:146`) so age rule can't fire; `last_donation_days` hard-coded 365 (`:161`); no pulse/temp inputs; saved `screening_tests.result` = serology only, engine decision ignored; raw CNIC (`:75`). |
| `pages/6_contracts.py` | 136 | ⚠️ | Models *vendor supply* contracts, not lend/borrow with return deadlines (differs from your spec). Status never becomes breached/expired. Sorted by SQL, not `merge_sort`. |
| `pages/7_transfusion.py` | 182 | ⚠️ | Imports from **both** engines (`:20`, `:152`). Transfusion inserted, then stock decremented in a *separate* transaction whose failure is ignored (`:119-121`). No stock check, no patient record link. |
| `pages/8_analytics.py` | 189 | ⚠️ | **Forecast input is `random.uniform`** (`:112-114`). `px.scatter_mapbox` is deprecated in current Plotly. Pie with 8 slices (`:95`). |
| `pages/9_ai_center.py` | 284 | ⚠️ | Random "historical usage" fed to LLM (`:81-82`); PII to LLM; unescaped chat HTML (`:179-186`). Correct `"staff"` check (`:38`). |
| `pages/10_admin.py` | 185 | ⚠️ | `_role != "admin"` (`:32`); role dropdown `staff/hospital/admin` (`:82`) violates the fresh-schema CHECK, and `add_user` swallows the `IntegrityError` → UI says "email may already exist" (`:103`). |
| `utils/database.py` | 403 | ⚠️ | Param-SQL ✅. No expiry filtering, no availability check, silent clamp (`:89-110`), connections never closed, no cache, no transactions across audit+write. |
| `utils/auth.py` | 23 | ⚠️ | SHA-256; `landing_page_for_role` unused. |
| `utils/sidebar.py` | 54 | ⚠️ | Role vocabulary `admin/hospital/staff` (`:5-14`). Hard-coded footer "NASTP-NIIT" (`:52`). |
| `utils/styles.py` | 592 | ⚠️ | Contrast failures (§7); `render_ai_response`, `alert_banner`, `styled_table` don't escape; Google-Fonts `@import` (`:28`). |
| `utils/helpers.py` | 226 | 🗑 mostly | Only `run_dsa_engine` is (indirectly) used, by the broken `test_connection.py`. `check_access` (`:223`) uses a **third** role vocabulary (`super_admin`). `pakistan_time()` is unused — no PKT handling anywhere. |
| `utils/dsa_engine.py` | 979 | ⚠️ | 13 ops + dispatcher; wrong data contract for SQLite (§3-#10); only `transfusion_monitor` is called. |
| `utils/ai_engine.py` | 393 | 🗑 | Rule-based screening strategies. Imported by nothing. |
| `utils/pdf_generator.py` | 297 | 🗑 | `generate_contract`, `generate_shift_report` — **never called**; README claims a "PDF shift report" on the dashboard (no `download_button` anywhere). |
| `utils/run.py` | 51 | 🗑 | Duplicate launcher; checks `.env` exists, pip-installs on every start. |
| `utils/__init__.py` | 2 | ✅ | |
| `dsa_engine.py` (root) | 471 | ⚠️ | What pages import. Full-mesh graph, exact-match routing, `All_Clear` bug, no dispatcher. Unused: `find_best_match`, `get_compatible_recipients`. |
| `ai_engine.py` (root) | 315 | ⚠️ | See §3-#14. |
| `setup_database.py` | 313 | ⚠️ | **Role names differ from pages** (`:39,194-204`). `input()` prompt (`:286`) blocks `run.bat`/CI. Seeds 10 donors, **0** contracts/exchanges/transfusions/patients/usage history. Units are `randint(0,60)` per group (not realistic proportions). `patients` table unused by any page. |
| `seed_data.py` | 238 | 🗑 | Supabase, string IDs, plaintext passwords. Crashes. |
| `test_connection.py` | 144 | 🗑 | Supabase; 3/10 checks fail on import. Not a test suite. |
| `antigravity.py` | 83 | 🗑 | Force layout; broken (`:1`), unreferenced. |
| `run.py` | 11 | ✅ | Plain launcher. |
| `run.bat` | 38 | ⚠️ | Calls `setup_database.py` (interactive prompt) on every start; prints demo creds. |
| `extras/10_hospital_mgmt.py`, `extras/11_my_profile.py` | 186 / 99 | 🗑 | Import deleted `utils.supabase_client`. Not in `pages/`, so never load. |
| `requirements.txt` | 11 | ⚠️ | §3-#8. |
| `.env.example` | 3 | ⚠️ | Supabase vars; no OpenRouter key. `HEAD` version contains a real-looking Supabase **dashboard URL/project ref**. |
| `.gitignore` | — | ✅ | Ignores `.env`, `*.db`, `build/`, `__pycache__`. |
| `lifeline.db` | 72 KB | ⚠️ | Built by an **older** schema: roles `admin/hospital/staff`, no other CHECKs, 0 indexes, `foreign_keys` off, rollback-journal mode. Rows: hospitals 8, users 11, blood_units 64, donors 10, requests 5, audit 5, ai_logs 14; **everything else 0**. |
| `build/` | 6.3 MB | 🗑 | CMake/MSVC output incl. `dsa_engine.exe` from the C++ era. Git-ignored. Safe to delete — **listed here, not touched**. |
| `README.md`, `PROJECT_REPORT.md`, `docs/PROJECT_REPORT.md`, `docs/DSA_MAPPING.md`, `DSA_ENGINE_DOCUMENTATION.md` | — | 📄 | All describe a different system than the code (§3-#5). |
| `logo.png` | — | ⚠️ | Modified in working tree; referenced by **no** code (README says "sidebar branding"; sidebar is text). |

---

## 5. Findings not on your list

### P0 — fix before anything else (clinical safety / correctness)

**P0-1 · Role vocabulary split → admins locked out on a fresh DB.**
`setup_database.py:39` CHECKs `super_admin | hospital_admin | staff`; every page, `sidebar.py:5-14` and `10_admin.py` use `admin | hospital | staff`; `helpers.check_access` uses a third. *Measured (fresh DB from `setup_database.py`):* super_admin sidebar shows **0/10** links, hospital_admin **0/10**; `10_admin.py` denies super_admin; `3_emergency.py:77` means no one can resolve requests. The checked-in DB (old vocabulary) shows 10/9/8 links, which is why it looks fine.

**P0-2 · `screen_donor` cannot return DEFER for any vital sign.** `All_Clear` always fires and overwrites the decision (§3-#13). Probes: Hb 9 → SAFE; weight 40 + SBP 200 → SAFE; pulse 130 + 38.5 °C → SAFE. Only serology (BLOCK/malaria DEFER) works.

**P0-3 · `transfusion_monitor` false negatives** (`utils/dsa_engine.py:528-573`, duplicated in root `:437-470`). Probes, all return **NORMAL / "Transfusion proceeding normally"**:
- SpO₂ 98→84 %, ΔBP −10, ΔT +0.2 (only `o2_post<90 AND bp_drop>40` triggers anaphylaxis)
- SBP 120→85 (Δ −35) with no temp change
- ΔT exactly +1.0 °C (strict `>`), or 37.7→38.6 °C (+0.9 but absolute 38.6)
- Pulse 75→150 (pulse is never read)
- Post vitals missing entirely (silent defaults to normal values)
Thresholds need a **written clinical reference + sign-off** (I will not invent them in Phase 3; I'll propose them for review). Also `fuzzy_severity` can never exceed 54/100 (all-severe peaks → MODERATE), so its SEVERE/CRITICAL labels are unreachable, and inputs past the last triangle score 0 → "MILD".

**P0-4 · Expired stock counts as available.** `get_blood_units`/`get_blood_summary` (`database.py:62-86`), dashboard KPIs, and `nearest_hospitals_with_blood` (`dsa_engine.py:100-105`) never filter `expiry_date`; nothing marks units expired. Seed hides it (all expiries in the future).

**P0-5 · Inventory can be over-consumed silently, and units have no identity.** `update_blood_units` (`database.py:89-110`) touches only the earliest-expiry row, clamps at 0, returns `True`. Probe: consume 9 999 from a 40-unit row → `True`, row = 0, no error. Pages 2 (`:165`) and 7 (`:121`) ignore the result; page 7 records the transfusion *before* and *outside* the decrement. `blood_units` is `(hospital, group, expiry, count)` — there is **no per-unit ID or status**, so your reserved → issued state machine and "double-issue impossible" requirement cannot be met without a schema change (Phase 2).

### P1

- **N6 · Success feedback never shown:** 12× `alert_banner(success)` immediately followed by `st.rerun()` (e.g. `2_inventory.py:143-145`).
- **N7 · HTML injection:** 77 `unsafe_allow_html` sites; user/LLM strings (patient names, notes, vendor, chat, AI text) are interpolated unescaped (`3_emergency.py:72`, `9_ai_center.py:179-186`, `styles.py:506-517,519-521,584-592`, `to_html(escape=False)` at `1_dashboard.py:133,159`). Streamlit strips `<script>`, but arbitrary markup/links/styling can spoof the UI (e.g. a fake "STOP TRANSFUSION" banner).
- **N8 · Fake data in decision paths:** dashboard `"+42 today"`, `"+12 this week"`, "35 % usage spike", "Dijkstra resolved Mayo→Jinnah 1.2 km" (`1_dashboard.py:67,85,171-172`); forecasts and AI prompts are fed `random.uniform` usage (`8_analytics.py:112-114`, `9_ai_center.py:81-82`). There is no usage-history table (`inventory_changes` is empty).
- **N9 · Features claimed but not real:** PDF shift report; `exchange_match`, `fefo_sort`, `merge_sort`, `bfs_backup`, `predict_shortage`, `cluster_donors`, `naive_bayes`, `waste_minimize`, `fuzzy_severity` (never called); exchange completion; emergency stock reservation; contract breach detection; "Admin → All 7 core algorithms" system test (README) — page 10 has no self-test.
- **N10 · Duplicate, drifting modules:** two `dsa_engine.py`, two `ai_engine.py`, two `run.py`, two differing `PROJECT_REPORT.md`. `screen_donor`/`risk_score` differ between copies (utils has pulse/temp/diabetes; root has weight). `transfusion_monitor` is in both.
- **N11 · No VCS safety net:** v6 code untracked/modified (see §1).
- **N12 · Fragile setup path:** `run.bat` runs `setup_database.py` every launch, which calls `input()` (`:286`) → `EOFError` non-interactively; answering "yes" deletes the DB.
- **N13 · DB hardening gaps:** no CHECK for blood group/status/urgency/units; probe on the old DB accepted group `"ZZ"` and `units=-5`; 0 indexes; `PRAGMA foreign_keys` set per connection only; not WAL; timestamps are naive server-local (`datetime.now()`), not PKT-aware; connections never explicitly closed; **no caching** (`st.cache_data` unused) — dashboard issues 1+N summary queries, analytics tab 3 issues N unit queries, several pages call `get_all_hospitals()` twice.
- **N14 · ML placeholders presented as models:** `naive_bayes_classify` trains on 10 hard-coded synthetic rows, and if training data has one class it **silently replaces the labels** (`utils/dsa_engine.py:757-771`); empty input returns "eligible, 0.98". `cluster_donors` with 2 donors → both REGULAR, meaningless; `waste_minimize` is unseeded (`random`), non-reproducible; `exchange_match` ignores units and ABO compatibility (matches any A+↔O+ swap even 1 unit vs 9); `dijkstra`/`bfs_backup` treat edges as directed (caller must add reverse edges; probe returned `None`).
- **N15 · Audit trail is thin:** no LOGIN/LOGOUT/failed-login events; `add_audit_log` is a separate transaction from the write it describes (crash between → unaudited change); descriptions are free text with no entity/before/after; no PKT.

### P2

- **Contrast (measured, WCAG AA 4.5:1):** `--text-muted` #4A5568 on #080B14 = **2.61** ✗; #94A3B8 on white = **2.56** ✗; EXPIRED pill = **2.31** ✗; white on `--red-bright` #FF2D55 (buttons, active tabs) = **3.65** ✗; white on your brand red #FF2D4F = **3.66** ✗ (brand red passes only as text on navy, **5.18**); blood-badge colours on the light theme: O+ 2.15 ✗, B- 2.80 ✗; success #00D68F on white 1.91 ✗. → Phase 5 needs a darker button red or large/bold-only use.
- **Brand mismatch:** UI uses #080B14 / #FF2D55, not #0D0A33 / #FF2D4F. Blood-group badges are colour + text (OK) but hues aren't colour-blind-checked.
- No `.streamlit/config.toml`; fonts (Inter, JetBrains Mono, Syne) load from Google's CDN — fails offline; `* {margin:0;padding:0}` global reset (`styles.py:52`) fights Streamlit's own layout; fixed-position sidebar footer (`sidebar.py:50-54`) can overlap on short screens.
- `px.scatter_mapbox` (`8_analytics.py:161`) is deprecated; tiles need internet. 8-slice pie violates your own chart rule (`:95`).
- Every page repeats ~15 lines of boilerplate (config, auth check, theme, sidebar, title block).
- Magic numbers: "critical" = <5 units network-wide (`database.py:395`) but hospital "CRITICAL" = <50 (`1_dashboard.py:122`); inventory bar capacity 200 (`1_dashboard.py:109`).
- Perf (informational): cold first page ≈ 2.9 s (imports), subsequent pages 0.0-0.5 s in `AppTest`. Not measured in a real browser; the <1.5 s target needs re-measuring in Phase 6.

---

## 6. Algorithm reality check (what the UI really runs)

| Doc/README says | Called by UI? | Where |
|---|---|---|
| Dijkstra | ✅ | pages 3, 4, 8, 9 via `HospitalGraph` (root) — degenerate on a full mesh |
| BFS backup | ❌ | `utils` only |
| FEFO min-heap | ❌ | Inventory sorts via SQL `ORDER BY expiry_date` |
| Merge sort | ❌ | Contracts sorts via SQL |
| Exchange hash-match | ❌ | Exchange page uses nearest-hospital search |
| Triage priority queue | ✅ | page 3 (`TriageQueue`) |
| Compatibility | ✅ | page 7 (`get_compatible_donors`) — correct |
| WMA forecast + shortage | ✅ | pages 8, 9 — **on random input** |
| screen_donor / risk_score | ✅ | page 5 — defects P0-2, double-penalty |
| transfusion_monitor | ✅ | page 7 (from `utils` copy) — defects P0-3 |
| predict_shortage (regression), K-Means, Naive Bayes, hill-climb, fuzzy | ❌ | `utils` only |

---

## 7. What works (keep)

- Every page loads without an exception for every role on the checked-in DB (30/30 page-role combos, `AppTest` with `st.page_link` stubbed — the harness itself can't render it).
- Page 9/10 "denied" gating works for the roles it names; staff correctly blocked from AI Center.
- Parameterised SQL throughout; FK declarations present.
- ABO/Rh table 64/64 correct; `get_compatible_donors` direction is right at the call site (`7_transfusion.py:116`).
- `TriageQueue` (stable tiebreak counter), `HospitalGraph.dijkstra` core (lazy-deletion heap) and `bfs_backup`/`dijkstra` in `utils` are correct on small known graphs.
- The app makes no network call unless the user clicks an AI button; with no key it returns a message rather than crashing.

---

## 8. Risk-ranked fix list → phase mapping

| Rank | Item | Phase |
|---:|---|---|
| 1 | Rotate the OpenRouter key; keep `.env` out of git (already true) | now (you) |
| 2 | Snapshot commit/branch of the v6 working tree | before Phase 1 |
| 3 | P0-1 unify roles (`super_admin/hospital_admin/staff`) across schema, pages, sidebar, helpers + RBAC decorator | 1 |
| 4 | bcrypt + migration; remove default password prefill; demo creds only when `APP_ENV=demo`; session timeout; login throttling; login/logout audit | 1 |
| 5 | P0-2/P0-3 screening + reaction rules rewritten against a **written reference table you approve**, with tests | 3 (table proposed in 3, needs your sign-off) |
| 6 | P0-4/P0-5 schema: per-unit rows + status state machine + CHECKs + indexes + transactional issue; expiry housekeeping | 2 |
| 7 | Single engine package, sparse k-NN road graph, compat-aware routing, one Dijkstra run, real `run_engine` registry on the new schema; delete the second engine | 3 |
| 8 | Real usage history (from issue/transfusion events) replacing `random` in forecasts/AI | 2-3 |
| 9 | AI client rewrite (one client, retry/backoff, `AIResult`, cache, rate limit, PII scrubber, escaped output, advisory label, audit logging) | 4 |
| 10 | PII masking in UI (CNIC) and scrub before LLM | 1 / 4 |
| 11 | Escape all interpolated strings; central components | 5 |
| 12 | Design tokens, WCAG-AA palette (§5-P2), component library, rebuild 9 pages | 5 |
| 13 | Caching, error/empty/loading states, self-test page, CI, Docker, Makefile | 6 |
| 14 | Rewrite README, add ARCHITECTURE/ALGORITHMS/CHANGELOG; delete the 5 stale docs and dead files (listed in §4) | 7 |

**Dead files to delete in Phase 7 (list only; nothing deleted yet):**
`seed_data.py`, `test_connection.py`, `antigravity.py` (or wire it), `extras/`, `utils/run.py`, `utils/helpers.py` (after salvaging `haversine`/`time_ago`), `utils/ai_engine.py`, `utils/pdf_generator.py` (or wire it), one of the two `dsa_engine.py`/`ai_engine.py`, `PROJECT_REPORT.md` (×2), `DSA_ENGINE_DOCUMENTATION.md`, `docs/DSA_MAPPING.md`, `build/`.

---

## 9. Assumptions & questions (one each; defaults chosen)

1. **Q:** May I make a snapshot commit (or a `v6-snapshot` branch) of the current working tree before Phase 1? *Default: yes, on a new branch, no push.*
2. **Q:** "Contracts" — your spec says lend/borrow with return deadlines and breaches; the current app has vendor supply contracts. *Default: implement the spec (hospital→hospital lend/borrow), migrate nothing since the table is empty.*
3. *Assumption:* the default role names are `super_admin | hospital_admin | staff` (already in the newest `setup_database.py`).
4. *Assumption:* clinical thresholds (reaction, screening) will be proposed in Phase 3 as a reference table for your/clinician review; until then I keep existing numbers and flag them.
5. *Assumption:* Python 3.10+ target (README) even though this machine runs 3.14.

---

## Appendix — probes run (scratch copies only)

| Probe | Result |
|---|---|
| ABO/Rh 64 pairs vs independent rule | 0 mismatches |
| Edges/node on 8-hospital graph; all paths from #1 direct? | 7; yes |
| A+ request, O- at H2, A+ at H3 | returns only H3 |
| `screen_donor` Hb 9 / wt 40 + SBP 200 / pulse 130 + 38.5 °C | SAFE / SAFE / SAFE (both copies) |
| `risk_score` HIV as disease + flag | two −100 penalties |
| `transfusion_monitor` SpO₂ 84 %; SBP −35; ΔT +1.0; +0.9→38.6; pulse 150; empty post | NORMAL ×6 |
| `fuzzy_severity` all-severe peaks | 54.0 → MODERATE |
| `update_blood_units(-9999)` on 40-unit row | `True`, row → 0 |
| `add_blood_units(group="ZZ", units=-5)` (old DB) | accepted |
| `setup_database.py` on fresh dir → roles | `super_admin 1, hospital_admin 4, staff 6` |
| Sidebar links, fresh DB: super_admin / hospital_admin / staff | 0 / 0 / 8 of 10 |
| Sidebar links, old DB: admin / hospital / staff | 10 / 9 / 8 of 10 |
| Page load, 10 pages × 3 roles × 2 DBs | 60/60 no exception; wrong-role denials as described |
| `python seed_data.py` / `python test_connection.py` | `KeyError: SUPABASE_URL` / 3 of 10 fail (`No module named utils.supabase_client`) |
| `import antigravity` | `NameError: name 'n' is not defined` |
| Git history scan for `sk-or-` / JWT-like keys, 5 revs | none |

---

## 10. Status after Phase 1 (security & foundation)

Items 1–4 and 8 of §3, P0-1, and the UI issues you reported are fixed on `main` (see `git log`). Everything else in §5 is still open and scheduled per §8.

| §3 item / finding | Status | Where |
|---|---|---|
| 1 key handling | **Done** except rotation (yours). `SecretStr`, no per-call `load_dotenv(override=True)`, never rendered | `lifeline/config.py`, `ai_engine.py` |
| 2 bcrypt / plaintext | **Done.** bcrypt (cost 12), 8-char/72-byte policy; legacy SHA-256 hashes verify and upgrade on next login; demo hashes upgraded at first start; `seed_data.py` deleted | `lifeline/auth/passwords.py`, `service.py`, `bootstrap.py` |
| 3 creds / timeout / throttle / per-page checks | **Done.** Demo table only if `APP_ENV=demo`; 30-min idle timeout; 5 failures → 15-min lock (also for unknown emails); guard on all 10 pages | `app.py`, `session.py`, `throttle.py`, `rbac.py` |
| 4 PII | **Done.** CNIC masked; LLM payloads pseudonymised/allow-listed; verified by tests that capture the HTTP body | `lifeline/privacy.py`, `pages/9_ai_center.py` |
| 8 requirements | **Done.** Upper bounds, bcrypt/pydantic(-settings) added, unused deps dropped, `requirements-dev.txt`. `folium`/`streamlit-folium` deferred to Phase 5 (emergency map) — nothing imports them yet | `requirements*.txt` |
| P0-1 role vocabulary | **Done.** `Role` enum; migration 001 converts old DBs (with automatic `.bak-v0` copy) | `lifeline/auth/roles.py`, `lifeline/db/` |
| §5-N15 audit gaps | Partly: LOGIN / LOGIN_FAILED / LOGIN_LOCKED / LOGOUT / SESSION_EXPIRED / ACCESS_DENIED are audited. PKT timestamps and before/after still open (Phase 2) | |
| Reported UI bugs | **Done:** duplicate sidebar nav, leaked `<div class="section-divider">` text, invisible light-mode text/forms/charts, footer overlap, login wordmark wrap/empty box | `.streamlit/config.toml`, `utils/styles.py`, `utils/sidebar.py`, `app.py` |

**Still open from this phase:** rotate the OpenRouter key; `setup_database.py`/legacy pages still use `utils/database.py` (moves to `lifeline/db/repositories` in Phase 2); `st.rerun()` swallowing success banners (§5-N6) and page-level HTML escaping of patient names (§5-N7) are Phase 5.

**Quality gates now:** `pytest` 100 passed; `ruff` and `mypy` clean on `lifeline/` and `tests/`; coverage of `lifeline/` 97 % (`auth/` ≥ 96 % per module except `create_admin`/`session`, both covered). Legacy modules (`pages/`, `utils/`, engines) are not yet under lint/type checks.

---

## 11. Status after Phase 2 (data layer)

| Finding | Status | Where |
|---|---|---|
| P0-4 expired stock counted as available | **Fixed.** Stock = `available` units with `expiry_date >= today`; housekeeping marks expired units and logs events | `units.py`, `housekeeping.py` |
| P0-5 silent over-consumption, no unit identity | **Fixed.** One row per unit; all-or-nothing FEFO issue (`InsufficientStock`); status changes are guarded UPDATEs inside `BEGIN IMMEDIATE`, so a unit cannot be issued twice (tested with 6 concurrent threads) | `lifeline/services/`, `db/connection.py` |
| State machine | **Done** in Python and as a DB trigger; a test checks all 36 (from, to) pairs agree | `constants.py`, `schema.sql` |
| N13 constraints/indexes/WAL | **Done.** CHECKs (groups, statuses, units > 0, coordinates, distinct hospitals), FKs, 24 indexes, unit blood group and expiry immutable, audit log append-only | `schema.sql` |
| N15 audit | **Done.** actor, action, entity, before/after JSON, PKT (`+05:00`) timestamps, written in the same transaction as the change | `repositories/audit.py` |
| N8 random forecast input | **Fixed.** Forecasts use real usage from `inventory_events`; the seed contains 30 days of history | `events.daily_usage` |
| N9 exchange never completes / request never reserves / contracts = vendor model | **Fixed.** request -> reserve -> dispatch/cancel; exchange request -> accept -> complete; lend/borrow contracts with deadlines and automatic BREACHED | `services/emergency.py`, `exchanges.py`, `contracts.py` |
| #7 IDs / seed | **Done.** One INTEGER-id schema; deterministic `random.Random(42)` seed (10 hospitals, 72 donors, ~460 available units, ~2,900 events, 644 transfusions, emergencies, exchanges, loans) | `scripts/seed_demo.py` |

**Migration 002** converts existing databases (aggregated counts become individual units; vendor contracts are kept as `vendor_contracts_legacy`; deltas become events; rows that cannot satisfy the new constraints go to `migration_rejects`, never dropped). A test asserts fresh and migrated schemas have identical shape. The first migration of a database writes `<db>.bak-v<N>` first.

**Known consequences:** a database whose stock had already passed its expiry date migrates to expired units (the checked-in demo DB from June is now all expired) - run `python -m scripts.setup_db --reset` for fresh demo data. Hospital coordinates in the seed are approximate (+-500 m) and the ABO/Rh group mix is an approximation of published Pakistani surveys; both are flagged in the seed file.

**Still open:** caching (`st.cache_data`) and structured logging (Phase 6); `utils/database.py` is a read-only transitional shim until the pages are rebuilt (Phase 5); routing still matches exact groups only and the graph is still a full mesh (Phase 3); screening/reaction rules unchanged (Phase 3).

**Quality gates:** `pytest` 313 passed; `ruff` + `mypy` clean on `lifeline/`, `tests/`, `scripts/`; coverage of `lifeline/` 96 %.
