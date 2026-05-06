# LIFELINE: Full Codebase & Architecture Breakdown

This document serves as the absolute, comprehensive guide to the **LIFELINE Blood Logistics Network**. It breaks down the entire project file by file, explaining the logic, architecture, Data Structures, Algorithms, Artificial Intelligence, and Software Engineering practices implemented.

---

## 1. Project Structure
The project is built on a **Microservices-inspired architecture** operating completely offline:
- **Frontend/Middleware**: Python & Streamlit (Multi-Page App).
- **Backend/Logic Engine**: Compiled C++ Binary (`dsa_engine.exe`).
- **Database**: Offline SQLite database (`lifeline.db`).

```text
📁 lifeline/
│-- 📄 app.py                  (Main entry point & Authentication)
│-- 📄 setup_database.py       (Database schema & mock data generation)
│-- 📄 dsa_engine.cpp          (Core AI and DSA algorithms)
│-- 📄 dsa_engine.exe          (Compiled C++ Engine)
│-- 📄 json.hpp                (C++ JSON Library)
│-- 📁 utils/
│   │-- 📄 helpers.py          (C++ Subprocess execution & Time formatting)
│   │-- 📄 sidebar.py          (Centralized UI Navigation)
│   │-- 📄 supabase_client.py  (SQLite Database interaction layer)
│-- 📁 pages/                  (Streamlit UI Modules)
│   │-- 1_dashboard.py to 9_admin.py
```

---

## 2. Core Backend: `dsa_engine.cpp` (DSA & AI)
This is the brain of the project. Because Python is too slow for massive graph routing and sorting, we offload all critical logic to C++. It takes JSON input, processes it, and returns JSON output.

### 2.1 FEFO Sort (Min-Heap Priority Queue)
**Subject: DSA**
```cpp
struct BloodUnit {
    string id, group, expiry;
    json original_data;
    bool operator>(const BloodUnit& other) const { return expiry > other.expiry; }
};
```
- **Explanation**: We define a `BloodUnit` struct. We overload the `>` operator to compare expiry dates.
- **Logic**: We use `priority_queue<BloodUnit, vector<BloodUnit>, greater<BloodUnit>> min_heap;`. This creates a **Min-Heap**. As we push blood units into the heap, it automatically sorts them in `O(log n)` time so that the unit closest to expiring is ALWAYS at the top. This implements **First-Expire-First-Out (FEFO)**.

### 2.2 Dijkstra's Algorithm (Weighted Graphs)
**Subject: DSA**
- **Explanation**: Used when a hospital requests emergency blood. We treat hospitals as **Nodes** and the distances between them as **Edges**.
- **Logic**: We build an adjacency list `unordered_map<string, vector<pair<string, float>>> adj;`.
- We initialize a priority queue `pq` and set the source distance to `0`, and all others to `1e9` (Infinity).
- The algorithm explores the network, constantly updating the shortest path `dist[v] = dist[u] + weight;`.
- Finally, it iterates over all `available_hospitals` to find the one with the absolute minimum distance from the source.

### 2.3 Breadth-First Search (BFS)
**Subject: DSA**
- **Explanation**: Used to find secondary "backup" hospitals if the primary target fails.
- **Logic**: We use a `queue<string> q;` and an `unordered_map<string, int> level;` to track the depth.
- Starting from the source, we explore all immediate neighbors (Level 1), then their neighbors (Level 2). This `O(V+E)` algorithm ensures we find the closest topological backup hospitals instantly.

### 2.4 Hash Maps (Exchange Matching)
**Subject: DSA**
- **Explanation**: Used in the Blood Exchange module.
- **Logic**: Instead of an `O(n^2)` nested loop to match hospitals wanting to trade blood, we use an `unordered_map<string, vector<json>> offer_map;`. We map the `needs_group` to the hospital. Thus, looking up a matching partner takes `O(1)` average time.

### 2.5 Risk Scoring (AI Heuristics)
**Subject: AI**
- **Explanation**: An AI heuristic algorithm that calculates donor safety.
- **Logic**: Starts with `score = 100`. It applies weighted deductive penalties:
  - If days since last donation < 90: `-15 points`
  - If on blood thinners: `-30 points`
  - If Diabetes: `-10 points`
  - If HIV/HepB: `-100 points` (Instant fail)
- The AI returns not just the score, but an "Explainable AI" array (`penalties`) so doctors understand *why* the score dropped.

### 2.6 Rule-Based Expert System (Forward Chaining)
**Subject: AI**
- **Explanation**: An Inference Engine for screening donors.
- **Logic**: We define a Knowledge Base (KB) of rules: `{"HIV", "contains", "HIV", "BLOCK", 10}`. 
- The engine iterates through the donor's vitals. If a rule triggers (`fired = true`), it pushes the consequence to the action list. The highest priority rule (e.g., Priority 10) dictates the final classification (`safe`, `caution`, `blocked`).

### 2.7 Merge Sort
**Subject: DSA**
- **Explanation**: Used to sort lending contracts by return deadlines.
- **Logic**: Implements a divide-and-conquer `mergeSort` function. It recursively splits the contract array in half, sorts the halves, and merges them back in `O(n log n)` time.

### 2.8 Model-Based Reflex Agent (Reaction Detection)
**Subject: AI**
- **Explanation**: Monitors live blood transfusions.
- **Logic**: The agent reads pre-transfusion and post-transfusion vitals. It calculates `temp_rise` and `bp_drop`. 
- Using predefined threshold models, it acts reflexively:
  - If O2 drops < 90 AND BP < 80 -> "ANAPHYLAXIS" -> "STOP. CODE BLUE."
  - If Temp rises > 2.0 AND BP drops > 30 -> "HEMOLYTIC" -> "STOP."
  - Else -> "NORMAL"

---

## 3. Python Backend & Middleware: `utils/`

### `utils/helpers.py`
This file is the bridge between Python and C++.
- `run_dsa_engine(operation, payload)`: This function converts a Python dictionary into a JSON string. It uses `subprocess.run` to execute `dsa_engine.exe`, passing the JSON string into the C++ standard input (`stdin`). It then captures the `stdout` from C++, parses it back into a Python dictionary, and returns it. This allows Streamlit to use C++ speeds seamlessly.

### `utils/supabase_client.py`
*(Note: Named supabase_client for legacy reasons, but implemented entirely in offline SQLite).*
- Contains all SQL queries.
- `auth_login(email, password)`: Hashes the password using SHA-256 and compares it against the `users` table.
- `get_dashboard_stats()`: Executes complex SQL aggregations (e.g., `SELECT blood_group, COUNT(*) FROM blood_units GROUP BY blood_group`) to feed the Analytics dashboard.
- `execute_query(sql, params)`: A secure wrapper that handles SQLite connections and cursors, preventing SQL injection by using parameterized queries `(?)`.

### `utils/sidebar.py`
- Implements the centralized navigation UI.
- Contains the custom CSS `[data-testid="stPageLink-Icon"] { display: none !important; }` which completely strips Streamlit's native emojis, leaving a highly professional text-only navigation menu that preserves session state without full page reloads.

---

## 4. Database Schema: `setup_database.py`

This script initializes the offline `lifeline.db` SQLite database. It is heavily utilized to inject massive amounts of realistic mock data.

**Key Tables**:
1. **`hospitals`**: Stores lat/lng coordinates (used by Dijkstra).
2. **`users`**: Stores hashed passwords and RBAC roles (`super_admin`, `hospital_admin`, `staff`).
3. **`donors` & `patients`**: Demographics and medical history. We inject **50 realistic male patients** here for testing.
4. **`blood_units`**: Tracks volume, collection date, expiry date, and storage temp.
5. **`contracts` & `exchange_offers`**: Tracks B2B blood sharing between hospitals.
6. **`audit_logs`**: Immutable ledger tracking every action in the system (logging who did what, when).

---

## 5. Frontend UI: `app.py` & `pages/`

**Global Styling (SE/UI):**
Every page injects a custom CSS block mapping to a modern **Glassmorphism** design:
```css
.stApp { background: linear-gradient(-45deg, #0f0c29, ...); }
.glass-card { backdrop-filter: blur(20px); background: rgba(20,20,35,0.7); border-radius: 16px; }
```

### `app.py`
- Acts as the Authentication Gatekeeper.
- If `st.session_state["logged_in"]` is false, it explicitly hides the sidebar and renders the Login UI. 
- Upon successful login, it triggers `st.rerun()`, forcing the app to load the authenticated state and revealing the global sidebar.

### `pages/1_dashboard.py` (Command Center)
- Fetches live statistics from the DB.
- Renders KPI cards (Wastage Rate, Contract Compliance).
- Features a "Generate Shift Report" button that uses the `reportlab` library to compile a downloadable PDF of current stock levels.

### `pages/2_inventory.py`
- Calls the C++ `fefo_sort` via `run_dsa_engine()` to sort blood units by expiry.
- Allows staff to register new blood bags, mapping them to Donors and logging the action to the Audit ledger.

### `pages/3_emergency.py`
- The most complex UI page.
- When an emergency is declared, it passes the source hospital and network graph to the C++ `dijkstra` and `bfs_backup` functions.
- Uses `folium` and `streamlit_folium` to render an interactive map, dynamically drawing PolyLines (paths) between the source hospital and the optimal target hospital identified by C++.

### `pages/4_exchange.py`
- Uses the C++ Hash Map matching algorithm. If a hospital requests an exchange, it instantly checks the pool for exact inverse matches.

### `pages/5_screening.py`
- Collects donor medical data via UI sliders and checkboxes.
- Passes the data to the C++ AI Expert System and Risk Scorer.
- Renders the resulting "Explainable AI" penalties and rule triggers on screen so doctors can make informed final decisions.

### `pages/6_contracts.py`
- Uses C++ Merge Sort to align contracts.
- Provides UI buttons to "Mark Returned", calculating if the blood was returned past the deadline and updating the database accordingly.

### `pages/7_transfusion.py`
- Live monitoring UI. Staff inputs Pre and Post transfusion vitals.
- The C++ Reflex Agent analyzes the vitals and throws massive Red/Amber/Green alerts to the screen (e.g., "HEMOLYTIC REACTION").

### `pages/8_analytics.py`
- Relies on `pandas` and `plotly.express`.
- We convert SQLite data into DataFrames (`df`).
- Renders `px.bar` and `px.pie` charts.
- Graphs are minimized to `height=250px` inside tight `.glass-card` elements to provide a dense, data-rich command interface.

### `pages/9_admin.py`
- Restricted to `super_admin` role.
- Reads the `audit_logs` table. Allows the admin to view the immutable ledger of system actions.

---

## 6. Conclusion
The LIFELINE architecture is a masterclass in modern software integration. By restricting Python/Streamlit to pure UI rendering and database querying, and pushing all heavy `O(n log n)` and `O((V+E) log V)` graph/sorting operations to a highly optimized C++ backend, the system achieves unprecedented speed. The integration of deterministic AI systems ensures medical safety rules are strictly enforced without black-box unpredictability.
