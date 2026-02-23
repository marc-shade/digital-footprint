from digital_footprint.db import Database


def test_database_creates_tables(tmp_db):
    cursor = tmp_db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    assert "persons" in tables
    assert "brokers" in tables
    assert "findings" in tables
    assert "removals" in tables
    assert "breaches" in tables
    assert "scans" in tables


def test_insert_person(tmp_db):
    person_id = tmp_db.insert_person(
        name="Marc Shade",
        emails=["marc@example.com"],
        phones=["555-0100"],
    )
    assert person_id == 1


def test_get_person(tmp_db):
    tmp_db.insert_person(name="Marc Shade", emails=["marc@example.com"])
    person = tmp_db.get_person(1)
    assert person is not None
    assert person.name == "Marc Shade"
    assert person.emails == ["marc@example.com"]


def test_list_persons(tmp_db):
    tmp_db.insert_person(name="Alice", emails=["alice@example.com"])
    tmp_db.insert_person(name="Bob", emails=["bob@example.com"])
    persons = tmp_db.list_persons()
    assert len(persons) == 2


def test_update_person(tmp_db):
    tmp_db.insert_person(name="Marc Shade", emails=["marc@example.com"])
    tmp_db.update_person(1, phones=["555-0100"])
    person = tmp_db.get_person(1)
    assert person.phones == ["555-0100"]


def test_insert_broker(tmp_db):
    from digital_footprint.models import Broker
    broker = Broker(slug="spokeo", name="Spokeo", url="https://spokeo.com", category="people_search")
    broker_id = tmp_db.insert_broker(broker)
    assert broker_id == 1


def test_get_broker_by_slug(tmp_db):
    from digital_footprint.models import Broker
    broker = Broker(slug="spokeo", name="Spokeo", url="https://spokeo.com", category="people_search")
    tmp_db.insert_broker(broker)
    result = tmp_db.get_broker_by_slug("spokeo")
    assert result is not None
    assert result.name == "Spokeo"


def test_list_brokers_by_category(tmp_db):
    from digital_footprint.models import Broker
    tmp_db.insert_broker(Broker(slug="spokeo", name="Spokeo", url="https://spokeo.com", category="people_search"))
    tmp_db.insert_broker(Broker(slug="acxiom", name="Acxiom", url="https://acxiom.com", category="marketing"))
    results = tmp_db.list_brokers(category="people_search")
    assert len(results) == 1
    assert results[0].slug == "spokeo"


def test_broker_stats(tmp_db):
    from digital_footprint.models import Broker
    tmp_db.insert_broker(Broker(slug="spokeo", name="Spokeo", url="https://spokeo.com", category="people_search", difficulty="easy", automatable=True))
    tmp_db.insert_broker(Broker(slug="acxiom", name="Acxiom", url="https://acxiom.com", category="marketing", difficulty="hard"))
    stats = tmp_db.broker_stats()
    assert stats["total"] == 2
    assert stats["by_category"]["people_search"] == 1
    assert stats["by_difficulty"]["easy"] == 1
    assert stats["automatable"] == 1


def test_get_status(tmp_db):
    tmp_db.insert_person(name="Marc", emails=["marc@example.com"])
    status = tmp_db.get_status()
    assert status["persons_count"] == 1
    assert status["brokers_count"] == 0
    assert status["findings"]["active"] == 0
