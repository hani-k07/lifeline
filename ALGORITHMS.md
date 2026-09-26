# Algorithms

Everything here is pure Python in `lifeline/engine/`: no I/O, no clock, no randomness (the one seeded exception is
K-Means). Every operation is reachable through one validated entry point:

```python
from lifeline.engine.dispatcher import run_engine, describe

run_engine("find_sources", {"nodes": [...], "source_id": 1, "blood_group": "A+", "stock": {"3": {"A+": 2}}})
```

Bad input raises `EngineError` with a plain message — never a bare `KeyError` and never a silently wrong answer.
`describe()` returns each operation's summary, complexity and PEAS description; a test fails if an operation is added
without them, or without a fixture in the self-test (Admin → System self-test).

## The 13 operations

| Operation | What it does | Time | Used by |
|---|---|---|---|
| `dijkstra` | Shortest road distance and path from one hospital to all others | O((V + E) log V) | Emergency, Exchange, Analytics |
| `bfs_backup` | Backup hospitals in fewest-hops order | O(V + E) | Emergency (backup options) |
| `find_sources` | Ranked blood sources: exact group first, then compatible groups, nearest first | O((V + E) log V + V·G) | Emergency, Exchange |
| `fefo_sort` | Dispatch order by earliest expiry; expired units set aside | O(n log n) | Inventory |
| `merge_sort` | Stable sort of records by a field | O(n log n) | Contracts (loans by deadline) |
| `exchange_match` | Suggest transfers that cover shortages from surpluses | O(S + D·G·C log C) | Exchange (suggestions) |
| `screen_donor` | Donor eligibility: every rule evaluated, every fired rule reported | O(r) | Screening |
| `risk_score` | 0–100 donor safety score from the same rules | O(r) | Screening |
| `transfusion_monitor` | Reaction check on pre/post vitals; missing data is UNKNOWN, never normal | O(r) | Transfusion |
| `fuzzy_severity` | Graded 0–100 severity from fuzzy memberships | O(1) | Transfusion (supplementary score) |
| `predict_shortage` | Per blood group: forecast, days to stock-out, risk, reorder quantity | O(G·(window·horizon + n)) | Analytics, AI Center |
| `cluster_donors` | K-Means donor segments: CORE / OCCASIONAL / LAPSED | O(n·k·iterations) | Analytics (donors) |
| `triage_order` | Open requests ordered by urgency, then waiting time | O(n log n) | Emergency (queue) |

V = hospitals, E = road links, G = blood groups (8), r = rules (a constant), n = records.

## Design notes

### Road network — `graph.py`
The original connected every hospital to every other, so the shortest path was always the direct edge and BFS had
nothing to explore. `build_road_graph` links each hospital to its **k = 3 nearest** neighbours only, weights each link by
haversine distance × **1.3** (a road is longer than a straight line), and adds bridging links if that leaves the network
in pieces, so every hospital stays reachable and multi-hop routes appear. Dijkstra uses a binary heap; it is verified
against Floyd–Warshall on the seeded network. Travel time (ETA) assumes an average urban ambulance speed of 20 km/h — an assumption, not a measurement.

### Blood sources — `routing.py`, `compatibility.py`
One Dijkstra run from the requesting hospital gives the distance to everyone (the old code re-ran it per candidate).
Sources are then ranked: **exact blood group first**, then compatible groups, **O− last** (the universal donor is
scarce and should not be spent on a patient who can take something else), nearest first inside each group. A source must
hold at least the minimum stock. ABO/Rh compatibility is one table, tested against an independent rule for all 64
donor/recipient pairs — an error here is a patient-safety defect.

### Expiry order — `sorting.py`
FEFO (first-expired-first-out) is a min-heap on (expiry date, id). Units past expiry are set aside, never dispatched;
units expiring within a window are flagged. `merge_sort` is a stable top-down merge sort (used to order loans by return
deadline); the dispatcher validates every record's key up front because a one-item list is never compared.

### Suggested transfers — `matching.py`
A hash index of surplus by blood group, then greedy allocation: biggest shortage first, exact group before compatible
ones (O− last), nearest surplus first. Deterministic. It is **greedy, not globally optimal** — it produces sensible
suggestions that a person accepts or ignores, and it reports the shortages it could not cover.

### Donor screening — `screening.py`
Forward chaining over a fixed rule base, no learning, fully explainable. **Every rule is evaluated and every rule that
fires is reported**; the decision is the most severe outcome (BLOCK > DEFER > SAFE). A donor is SAFE only when nothing
fired *and* every required measurement was supplied — a missing value is DEFER, never assumed normal. The old engine
defaulted absent vitals to healthy numbers and ended with an "All_Clear" rule that overwrote every DEFER. `risk_score`
is built from the same rules, so it can never disagree with the decision.

### Reaction monitor — `transfusion.py`
A reflex agent over pre/post vitals (temperature, systolic BP, pulse, SpO₂). It reports every rule that fired and the
highest severity; a missing vital is UNKNOWN ("cannot assess"), never normal; physiologically impossible values are
rejected as data-entry errors. It recommends "stop and assess" and never diagnoses. The fuzzy score uses shoulder
memberships (a value beyond the severe point stays fully severe) combined with a probabilistic OR; it is a
supplementary graded view — the reflex rules decide what staff are told to do.

### Demand forecast — `forecasting.py`
Weighted moving average (recent days count more; each forecast day feeds the next) over **real** daily usage from the
inventory event ledger — never random numbers. `history` ends yesterday (a half-finished day would drag the forecast
down) and the forecast starts today. An ordinary-least-squares slope gives the trend. `shortage_risk` compares
cumulative forecast demand with current stock to give a risk level, the day of stock-out and a reorder quantity
(with a safety buffer).

### Donor segments — `clustering.py`
K-Means written from scratch on standardised age, number of donations and days since the last donation (capped at two
years), k-means++ seeding from a fixed seed so results repeat. Segments are named from the cluster **centres**, not
from cluster numbers, so the names mean the same thing every run: LAPSED (longest since last donation — re-engage
first), CORE (most frequent of the rest), OCCASIONAL (everyone else).

### Emergency queue — `triage.py`
A binary min-heap on (urgency rank, arrival time, id): CRITICAL before URGENT before ROUTINE, oldest first inside a
level. Both the Emergency page and the AI Center show this order; the AI is only ever a second opinion on it.

## PEAS summaries

Each agent-style operation carries its PEAS description in `OPERATIONS` (visible through `describe()`):

| Agent | Performance | Environment | Actuators | Sensors |
|---|---|---|---|---|
| Routing | Safe blood arrives fast, O− spared | Road network + stock | Ranked options | Stock, distances |
| Screening | No unsafe donor cleared; every reason visible | One donor's intake | SAFE/DEFER/BLOCK + rules | Serology, vitals, history |
| Reaction monitor | No reaction reported as normal; no guessing | One transfusion | Severity + action | Temperature, BP, pulse, SpO₂ |
| Supply planning | Shortage flagged early enough to reorder | Usage history + stock | Risk, days to stock-out, reorder | Daily usage, stock now |
| Triage | Most urgent handled first | Open requests | Work list | Urgency, created_at |
| Donor engagement | Outreach to the right donors | Donor registry | Segment per donor | Age, donations, recency |

## Removed on purpose

- `naive_bayes_classify` — it trained on invented data, so its output had no meaning.
- `waste_minimize` — its input was random.

## Clinical thresholds

Every cut-off lives in `lifeline/engine/thresholds.py` and is mirrored in
[docs/CLINICAL_REFERENCE.md](docs/CLINICAL_REFERENCE.md); a test parses the document and fails if any value differs
from the code, and every threshold is tested at its boundary. **The values are proposals awaiting clinical sign-off.**
