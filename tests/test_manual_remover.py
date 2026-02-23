"""Tests for manual removal instruction generator."""

from digital_footprint.removers.manual_remover import ManualRemover


def test_generate_phone_instructions():
    remover = ManualRemover()
    result = remover.submit(
        person={"name": "John Doe", "email": "john@example.com", "phone": "555-1234"},
        broker={
            "name": "TestBroker",
            "opt_out": {
                "method": "phone",
                "phone": "1-800-555-0000",
                "steps": ["Call the number", "Request removal", "Provide your name"],
            },
        },
    )
    assert result["status"] == "instructions_generated"
    assert "1-800-555-0000" in result["instructions"]
    assert "John Doe" in result["instructions"]


def test_generate_mail_instructions():
    remover = ManualRemover()
    result = remover.submit(
        person={"name": "John Doe", "email": "john@example.com"},
        broker={
            "name": "MailBroker",
            "opt_out": {
                "method": "mail",
                "mail_address": "123 Privacy Lane, Austin, TX",
                "steps": ["Write a letter", "Mail it"],
            },
        },
    )
    assert result["status"] == "instructions_generated"
    assert "123 Privacy Lane" in result["instructions"]


def test_generate_with_no_steps():
    remover = ManualRemover()
    result = remover.submit(
        person={"name": "John Doe", "email": "john@example.com"},
        broker={"name": "MinimalBroker", "opt_out": {"method": "phone"}},
    )
    assert result["status"] == "instructions_generated"
    assert "MinimalBroker" in result["instructions"]
