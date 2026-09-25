-- Unify role names (admin -> super_admin, hospital -> hospital_admin) and add login throttling.
-- Rebuild is required because SQLite cannot alter a CHECK constraint. The runner turns
-- foreign_keys OFF around this file and runs PRAGMA foreign_key_check afterwards.
BEGIN;

CREATE TABLE users_new (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK(role IN ('super_admin','hospital_admin','staff')),
    name          TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    hospital_id   INTEGER REFERENCES hospitals(id)
);

INSERT INTO users_new (id, email, password_hash, role, name, created_at, hospital_id)
SELECT id, email, password_hash,
       CASE role WHEN 'admin' THEN 'super_admin' WHEN 'hospital' THEN 'hospital_admin' ELSE role END,
       name, created_at, hospital_id
FROM users;

DROP TABLE users;
ALTER TABLE users_new RENAME TO users;

CREATE TABLE IF NOT EXISTS login_throttle (
    email        TEXT PRIMARY KEY,
    failed_count INTEGER NOT NULL DEFAULT 0,
    locked_until INTEGER NOT NULL DEFAULT 0,   -- unix seconds
    updated_at   INTEGER NOT NULL
);

PRAGMA user_version = 1;
COMMIT;
