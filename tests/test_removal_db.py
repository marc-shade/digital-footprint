"""Tests for removal CRUD operations in Database."""

from datetime import datetime, timedelta


def test_insert_removal(tmp_db):
    person_id = tmp_db.insert_person("Test Person", emails=["test@example.com"])
    broker = _insert_test_broker(tmp_db)
    removal_id = tmp_db.insert_removal(
        person_id=person_id,
        broker_id=broker.id,
        method="email",
        status="submitted",
        reference_id="REF-001",
    )
    assert removal_id > 0


def test_get_removals_by_person(tmp_db):
    person_id = tmp_db.insert_person("Test Person", emails=["test@example.com"])
    broker = _insert_test_broker(tmp_db)
    tmp_db.insert_removal(person_id=person_id, broker_id=broker.id, method="email")
    tmp_db.insert_removal(person_id=person_id, broker_id=broker.id, method="web_form")
    removals = tmp_db.get_removals_by_person(person_id)
    assert len(removals) == 2


def test_update_removal(tmp_db):
    person_id = tmp_db.insert_person("Test Person", emails=["test@example.com"])
    broker = _insert_test_broker(tmp_db)
    removal_id = tmp_db.insert_removal(
        person_id=person_id,
        broker_id=broker.id,
        method="email",
        status="pending",
    )
    tmp_db.update_removal(removal_id, status="submitted", submitted_at=datetime.now().isoformat())
    removals = tmp_db.get_removals_by_person(person_id)
    assert removals[0]["status"] == "submitted"
    assert removals[0]["submitted_at"] is not None


def test_get_pending_verifications(tmp_db):
    person_id = tmp_db.insert_person("Test Person", emails=["test@example.com"])
    broker = _insert_test_broker(tmp_db)
    past = (datetime.now() - timedelta(days=1)).isoformat()
    future = (datetime.now() + timedelta(days=30)).isoformat()
    tmp_db.insert_removal(person_id=person_id, broker_id=broker.id, method="email", status="submitted", next_check_at=past)
    tmp_db.insert_removal(person_id=person_id, broker_id=broker.id, method="email", status="submitted", next_check_at=future)
    pending = tmp_db.get_pending_verifications()
    assert len(pending) == 1


def test_get_removal_by_id(tmp_db):
    person_id = tmp_db.insert_person("Test Person", emails=["test@example.com"])
    broker = _insert_test_broker(tmp_db)
    removal_id = tmp_db.insert_removal(person_id=person_id, broker_id=broker.id, method="email")
    removal = tmp_db.get_removal(removal_id)
    assert removal is not None
    assert removal["method"] == "email"


def _insert_test_broker(db):
    from digital_footprint.models import Broker
    broker = Broker(slug="testbroker", name="TestBroker", url="https://test.com", category="people_search")
    db.insert_broker(broker)
    return db.get_broker_by_slug("testbroker")
