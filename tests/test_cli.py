"""Tests for the dfp CLI."""

from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from digital_footprint.cli import cli
from digital_footprint.models import Person


@patch("digital_footprint.cli._get_db")
def test_person_add(mock_db):
    db = MagicMock()
    db.insert_person.return_value = 1
    mock_db.return_value = db

    runner = CliRunner()
    result = runner.invoke(cli, ["person", "add", "John Doe", "-e", "john@test.com"])
    assert result.exit_code == 0
    assert "Added person" in result.output
    assert "John Doe" in result.output
    db.insert_person.assert_called_once()


@patch("digital_footprint.cli._get_db")
def test_person_list(mock_db):
    db = MagicMock()
    db.list_persons.return_value = [
        Person(id=1, name="John Doe", relation="self", emails=["john@test.com"]),
    ]
    mock_db.return_value = db

    runner = CliRunner()
    result = runner.invoke(cli, ["person", "list"])
    assert result.exit_code == 0
    assert "John Doe" in result.output


@patch("digital_footprint.cli._get_db")
def test_person_list_empty(mock_db):
    db = MagicMock()
    db.list_persons.return_value = []
    mock_db.return_value = db

    runner = CliRunner()
    result = runner.invoke(cli, ["person", "list"])
    assert result.exit_code == 0
    assert "No persons" in result.output


@patch("digital_footprint.cli._get_db")
def test_person_show(mock_db):
    db = MagicMock()
    db.get_person.return_value = Person(
        id=1, name="John Doe", relation="self",
        emails=["john@test.com"], phones=["555-1234"],
    )
    mock_db.return_value = db

    runner = CliRunner()
    result = runner.invoke(cli, ["person", "show", "1"])
    assert result.exit_code == 0
    assert "John Doe" in result.output
    assert "john@test.com" in result.output


@patch("digital_footprint.cli._get_db")
def test_person_show_not_found(mock_db):
    db = MagicMock()
    db.get_person.return_value = None
    mock_db.return_value = db

    runner = CliRunner()
    result = runner.invoke(cli, ["person", "show", "999"])
    assert result.exit_code != 0


@patch("digital_footprint.cli._get_db")
def test_status(mock_db):
    db = MagicMock()
    db.list_persons.return_value = [MagicMock()]
    db.list_brokers.return_value = [MagicMock()] * 5
    mock_db.return_value = db

    runner = CliRunner()
    with patch("digital_footprint.cli.get_config") as mock_config:
        mock_config.return_value = MagicMock(
            db_path="/tmp/test.db",
            hibp_api_key="test",
            smtp_host="smtp.test.com",
        )
        result = runner.invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "Persons protected: 1" in result.output
    assert "Brokers loaded:    5" in result.output


def test_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "1.0.0" in result.output


@patch("digital_footprint.cli._get_db")
def test_broker_list(mock_db):
    db = MagicMock()
    broker = MagicMock()
    broker.slug = "test-broker"
    broker.name = "Test Broker"
    broker.category = "people-search"
    broker.opt_out_method = "web_form"
    db.list_brokers.return_value = [broker]
    mock_db.return_value = db

    runner = CliRunner()
    result = runner.invoke(cli, ["broker", "list"])
    assert result.exit_code == 0
    assert "Test Broker" in result.output
