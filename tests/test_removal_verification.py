"""Tests for removal verification (re-scan to confirm)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from digital_footprint.removers.verification import RemovalVerifier


@pytest.mark.asyncio
@patch("digital_footprint.removers.verification.scan_broker")
async def test_verify_confirmed(mock_scan):
    mock_scan.return_value = MagicMock(found=False)

    verifier = RemovalVerifier()
    result = await verifier.verify_single(
        removal={
            "id": 1,
            "broker_slug": "spokeo",
            "broker_name": "Spokeo",
            "person_first_name": "John",
            "person_last_name": "Doe",
            "search_url_pattern": "https://spokeo.com/{first}-{last}",
            "attempts": 0,
        },
    )
    assert result["status"] == "confirmed"


@pytest.mark.asyncio
@patch("digital_footprint.removers.verification.scan_broker")
async def test_verify_still_found(mock_scan):
    mock_scan.return_value = MagicMock(found=True)

    verifier = RemovalVerifier()
    result = await verifier.verify_single(
        removal={
            "id": 1,
            "broker_slug": "spokeo",
            "broker_name": "Spokeo",
            "person_first_name": "John",
            "person_last_name": "Doe",
            "search_url_pattern": "https://spokeo.com/{first}-{last}",
            "attempts": 1,
        },
    )
    assert result["status"] == "still_found"
    assert result["attempts"] == 2


@pytest.mark.asyncio
@patch("digital_footprint.removers.verification.scan_broker")
async def test_verify_max_attempts_reached(mock_scan):
    mock_scan.return_value = MagicMock(found=True)

    verifier = RemovalVerifier()
    result = await verifier.verify_single(
        removal={
            "id": 1,
            "broker_slug": "spokeo",
            "broker_name": "Spokeo",
            "person_first_name": "John",
            "person_last_name": "Doe",
            "search_url_pattern": "https://spokeo.com/{first}-{last}",
            "attempts": 3,
        },
    )
    assert result["status"] == "failed"


@pytest.mark.asyncio
@patch("digital_footprint.removers.verification.scan_broker")
async def test_verify_scan_error(mock_scan):
    mock_scan.return_value = MagicMock(found=False, error="Timeout")

    verifier = RemovalVerifier()
    result = await verifier.verify_single(
        removal={
            "id": 1,
            "broker_slug": "spokeo",
            "broker_name": "Spokeo",
            "person_first_name": "John",
            "person_last_name": "Doe",
            "search_url_pattern": "https://spokeo.com/{first}-{last}",
            "attempts": 0,
        },
    )
    # Not found but had error -- still counts as confirmed (conservative)
    assert result["status"] == "confirmed"
