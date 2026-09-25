# LIFELINE v5.0 — Intelligent Blood Logistics Network

Streamlit + Supabase blood bank management system for Lahore hospital network with pure-Python DSA/AI engine.

## Architecture

- **Frontend:** Streamlit multipage app (`app.py`, `pages/1-9`)
- **Database:** Supabase (cloud PostgreSQL)
- **Algorithms:** `utils/dsa_engine.py` — 13 operations via `run_engine()`
- **Data layer:** `utils/supabase_client.py` — all DB access

## Setup

### 1. Prerequisites

- Python 3.10+
- Supabase project with tables (run seed script)

### 2. Install

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | `https://<project-id>.supabase.co` |
| `SUPABASE_KEY` | Supabase anon or service role key |

### 4. Seed database

```bash
python seed_data.py
```

### 5. Verify

```bash
python test_connection.py
```

### 6. Run

```bash
python run.py
# or
streamlit run app.py
```

## Demo Credentials

| Email | Password | Role |
|-------|----------|------|
| admin@lifeline.com | lifeline123 | Super Admin |
| mayo@lifeline.com | lifeline123 | Hospital Admin |
| services@lifeline.com | lifeline123 | Hospital Admin |
| staff@lifeline.com | lifeline123 | Staff |

## Modules

| Page | Feature | DSA Algorithm |
|------|---------|---------------|
| Dashboard | KPIs, PDF shift report | predict_shortage |
| Inventory | FEFO sorted stock | fefo_sort |
| Emergency | Route + map | dijkstra, bfs_backup |
| Exchange | Blood swaps | exchange_match |
| Screening | Donor eligibility | screen_donor, risk_score |
| Contracts | Deadline tracking | merge_sort |
| Transfusion | Reaction monitor | transfusion_monitor, fuzzy_severity |
| Analytics | Forecasts, clustering | predict_shortage, cluster_donors, waste_minimize |
| Admin | Audit, users, system test | All 7 core algorithms |

## Troubleshooting

**`EnvironmentError: SUPABASE_URL and SUPABASE_KEY must be set`**
- Copy `.env.example` to `.env` and add valid credentials.

**`auth_login` fails**
- Run `python seed_data.py` to create demo users.

**Empty dashboard**
- Seed data populates hospitals, units, contracts. Re-run seed script.

**Import errors for sklearn/numpy**
- `pip install -r requirements.txt` with Python 3.10+.

## Project Structure

```
lifelineold/
├── app.py                 # Login gate
├── run.py                 # Launcher
├── seed_data.py           # Supabase seed
├── test_connection.py     # Health checks
├── logo.png               # Sidebar branding
├── pages/                 # 9 Streamlit modules
└── utils/
    ├── dsa_engine.py      # 13 algorithms
    ├── supabase_client.py # DB layer
    ├── helpers.py         # run_dsa_engine wrapper
    ├── styles.py          # Glassmorphism CSS
    └── sidebar.py         # Navigation
```
