# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com). This release is the result of the engineering audit in
[AUDIT.md](AUDIT.md); finding numbers (P0-n, N-n) refer to it.

## [6.0.0] — unreleased

### Security
- Passwords are hashed with **bcrypt** (cost 12); the old unsalted SHA-256 hashes (one shared hash for all 11 seeded
  users) still verify and are upgraded on the next login. The demo password is no longer pre-filled in the admin form.
- **Login throttle**: 5 failures lock an email for 15 minutes, including unknown emails so responses do not reveal
  which accounts exist. **30-minute idle timeout**; expired sessions fail closed.
- **Authorisation on every page and inside every service call**, not just in the sidebar. A page that is not in the
  access table is closed. Every denial is audited.
- Demo credentials are shown on the login page **only** when `APP_ENV=demo`.
- The OpenRouter key is a `SecretStr`, never rendered or logged. Log lines are redacted for API keys, bcrypt hashes,
  CNIC, phone numbers and emails.
- **Privacy**: CNIC is masked on screen; the AI receives only "Patient N" pseudonyms and allow-listed, scrubbed fields.
  Tests capture the outgoing HTTP body and search it for every real name and identifier in the database.

### Fixed — patient-safety defects
- **P0-2 Donor screening never deferred on vitals** (haemoglobin 9, weight 40, systolic 200, pulse 130 and 38.5 °C all
  returned SAFE): every rule is now evaluated, every rule that fires is reported, and a missing measurement is DEFER.
- **P0-3 Reaction monitor missed real reactions** (SpO₂ 84 %, a 35 mmHg pressure drop and pulse 150 were all "NORMAL"):
  rewritten against a written table; missing vitals are UNKNOWN, never normal.
- **P0-4 Expired blood counted as stock**: stock is available units whose expiry date has not passed; a housekeeping
  sweep marks the rest expired and logs it.
- **P0-5 Silent over-consumption**: issuing 9,999 units of a 40-unit row "succeeded" and zeroed it. Issuing is now
  all-or-nothing and reports the shortfall.
- **Routing offered only the exact blood group** (an O− unit never appeared for an A+ patient) and re-ran Dijkstra per
  candidate. One run now ranks exact group first, then compatible groups with O− last.
- The road network was a complete graph, so BFS and multi-hop routes were meaningless; it is now sparse (3 nearest × 1.3).
- Forecasts were fed random numbers; they now use real usage from the inventory event ledger.
- Emergency requests never reserved stock and exchanges never completed. Request → reserve → dispatch/cancel and
  exchange request → accept → complete are real workflows; loans between hospitals have deadlines and flag themselves
  when overdue. Creating a request and reserving its blood is one atomic step.
- Dashboard hospital status was "critical" almost everywhere because rare groups are naturally scarce; it now weighs A+, B+, O+ and O−.

### Added
- **Per-unit blood ledger** with a state machine (available → reserved → issued/transfused, or expired/discarded)
  enforced in Python *and* by a database trigger; unit blood group and expiry are immutable; the audit log is append-only
  and records actor, entity, before/after and a Pakistan-time timestamp.
- Numbered **migrations** (`PRAGMA user_version`) with an automatic backup and a `migration_rejects` table instead of
  dropping rows; a test asserts fresh and migrated schemas are identical.
- **Engine dispatcher** `run_engine()` with 13 validated operations, complexity and PEAS metadata.
- **Design system**: tokens, dark and light themes that pass WCAG AA (tested), colour-blind-safe blood-group badges
  (label always shown, Rh− outlined), hatched chart bars, no pie charts, empty/error states everywhere, two-step
  confirmation on irreversible actions, inline validation, tablet layout.
- All ten pages rebuilt; the emergency flow is a three-step wizard with a route map.
- **Admin → System self-test**: runs every engine operation against a known answer and checks database health.
- **AI Center** labels every answer "AI suggestion — verify clinically", says so when no key is configured, shows a failed
  call as a warning rather than an answer, and logs real answers.
- Structured JSON logging with rotation; CI (ruff, mypy, tests, 90 % coverage floor on `engine/` and `auth/`),
  `Dockerfile`, `Makefile`, `.env.example`.
- ~580 automated tests, including a brute-force check of all 64 ABO/Rh pairs, Dijkstra against
  Floyd–Warshall, a six-thread double-issue race, and a per-page 1.5 s render budget.
- [docs/CLINICAL_REFERENCE.md](docs/CLINICAL_REFERENCE.md): every clinical cut-off in one table, checked against the code by a test.
- README rewrite, [ARCHITECTURE.md](ARCHITECTURE.md), [ALGORITHMS.md](ALGORITHMS.md).

### Changed
- **Two deliberate clinical changes need sign-off**: syphilis is now DEFER (the old code said BLOCK while its own
  message said "defer until treated"), and blood thinners now defer a donor.
- Database is SQLite only; the dead Supabase code is gone.
- Dependencies: pinned with upper bounds; `bcrypt`, `pydantic` and `pydantic-settings` added; `numpy`, `scikit-learn`,
  `pytz` and `reportlab` removed (nothing used them any more).
- Charts fit their axis labels; the stock grid is four columns; the login page is centred.

### Removed
- Duplicate and dead modules: the two `dsa_engine.py`, two `ai_engine.py` copies (one kept), `antigravity.py`,
  `seed_data.py`, `test_connection.py`, `utils/styles.py`, `utils/sidebar.py`, `utils/pdf_generator.py` (never called),
  `utils/run.py`, `extras/`.
- Stale documents: both `PROJECT_REPORT.md` files, `DSA_ENGINE_DOCUMENTATION.md`, `docs/DSA_MAPPING.md`.
- Algorithms with no honest input: `naive_bayes_classify` (invented training data) and `waste_minimize` (random input).

### Not done / needs a person
- **AI client rewrite** (retries with backoff, response caching, rate limiting, a dedicated PII-scrubber module) was
  skipped by choice. The page-level behaviour above is done; the client in `ai_engine.py` is still the original.
- **Clinical review** of the proposed thresholds.
- **Rotate the OpenRouter key** in your local `.env`.
- The Docker image has not been built or run in CI.
- `build/` (6 MB of CMake output from the C++ era, git-ignored) is still on disk; delete it when you like.
