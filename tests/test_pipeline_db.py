"""Tests for pipeline_runs DB operations."""

import json

from tests.conftest import make_test_db


def test_insert_pipeline_run():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    run_id = db.insert_pipeline_run(
        person_id=1,
        started_at="2026-02-23 10:00:00",
    )
    assert run_id > 0


def test_update_pipeline_run():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    run_id = db.insert_pipeline_run(person_id=1, started_at="2026-02-23 10:00:00")
    db.update_pipeline_run(
        run_id,
        status="completed",
        completed_at="2026-02-23 10:05:00",
        breaches_found=3,
        risk_score=45,
    )
    run = db.get_pipeline_run(run_id)
    assert run["status"] == "completed"
    assert run["breaches_found"] == 3
    assert run["risk_score"] == 45


def test_get_pipeline_runs_by_person():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    db.insert_pipeline_run(person_id=1, started_at="2026-02-23 08:00:00")
    db.insert_pipeline_run(person_id=1, started_at="2026-02-23 14:00:00")

    runs = db.get_pipeline_runs(person_id=1)
    assert len(runs) == 2
    # Most recent first
    assert runs[0]["started_at"] == "2026-02-23 14:00:00"


def test_get_pipeline_runs_empty():
    db = make_test_db()
    runs = db.get_pipeline_runs(person_id=999)
    assert len(runs) == 0


def test_get_pipeline_run_by_id():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    run_id = db.insert_pipeline_run(person_id=1, started_at="2026-02-23 10:00:00")
    run = db.get_pipeline_run(run_id)
    assert run is not None
    assert run["person_id"] == 1


def test_get_pipeline_run_not_found():
    db = make_test_db()
    assert db.get_pipeline_run(999) is None
