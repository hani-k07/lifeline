"""Create, migrate or reset the database.

    python -m scripts.setup_db            new DB: schema + demo data (schema + hospitals only when APP_ENV=prod)
                                          existing DB: migrate to the latest schema, keep the data
    python -m scripts.setup_db --reset    delete the DB and recreate it
    python -m scripts.setup_db --empty    schema + hospitals only, no demo users or sample data
"""
from __future__ import annotations

import argparse
import sqlite3

from lifeline.config import get_settings
from lifeline.db.migrate import apply_migrations
from lifeline.db.schema import create_schema
from scripts.seed_demo import seed_demo, seed_reference


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create/seed or migrate the LIFELINE database.")
    parser.add_argument("--reset", action="store_true", help="delete the existing database and recreate it")
    parser.add_argument("--empty", action="store_true", help="no demo users or sample data")
    args = parser.parse_args(argv)

    settings = get_settings()
    path = settings.db_path
    print("[*] LIFELINE database setup")
    if path.exists() and not args.reset:
        conn = sqlite3.connect(path)
        applied = apply_migrations(conn)
        conn.close()
        print(f"   -> Existing database kept ({'migrated to v' + str(applied[-1]) if applied else 'already up to date'}).")
        print("   -> Use --reset to delete and recreate it.")
        return 0
    if args.reset:
        for suffix in ("", "-wal", "-shm", "-journal"):
            path.with_name(path.name + suffix).unlink(missing_ok=True)
        print("   -> Old database deleted.")

    conn = sqlite3.connect(path)
    create_schema(conn)
    if args.empty or settings.app_env == "prod":
        seed_reference(conn)
        conn.close()
        print("   -> Schema and hospitals created; no demo users or sample data.")
        print("   -> Create the first super admin with: python -m lifeline.auth.create_admin")
        return 0
    print("   -> Seeding demo data (deterministic, seed 42)...")
    seed_demo(conn)
    conn.close()
    print("[+] Database ready. Run: streamlit run app.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
