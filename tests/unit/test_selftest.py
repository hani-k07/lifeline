from lifeline import selftest


def test_self_test_passes_on_a_healthy_demo_database(demo_db):
    results = selftest.run_all()
    failed = [(r.name, r.detail) for r in results if not r.ok]
    assert not failed, failed
    assert {r.area for r in results} == {"Engine", "Database"}
    assert len(results) >= 15


def test_a_broken_check_is_reported_not_raised(demo_db, monkeypatch):
    monkeypatch.setitem(selftest.CHECKS, "Deliberately wrong", ("triage_order", {"requests": [{"id": 1, "urgency": "ROUTINE"}]},
                                                                lambda r: r["ordered"][0]["id"] == 99))
    monkeypatch.setitem(selftest.CHECKS, "Deliberately invalid", ("dijkstra", {"nodes": []}, lambda r: True))
    failed = {r.name: r.detail for r in selftest.run_all() if not r.ok}
    assert set(failed) == {"Deliberately wrong", "Deliberately invalid"}
    assert "known answer" in failed["Deliberately wrong"] and "nodes" in failed["Deliberately invalid"]


def test_a_stale_schema_is_flagged(demo_db):
    from lifeline.db.connection import connect
    with connect() as conn:
        conn.execute("PRAGMA user_version = 1")
    failed = [r for r in selftest.run_all() if not r.ok]
    assert [r.name for r in failed] == ["Schema is up to date"]
