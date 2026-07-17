"""Tests for removal verification (re-scan to confirm).

The mocks return realistic BrokerScanResult objects (with status + blocked)
because verify_single now distinguishes confirmed / still-listed / unverifiable
instead of treating every found=False as 'removed'.
"""

import pytest
from unittest.mock import AsyncMock, patch
from digital_footprint.removers.verification import RemovalVerifier
from digital_footprint.scanners.broker_scanner import BrokerScanResult


def _result(**kw):
    base = dict(broker_slug="spokeo", broker_name="Spokeo",
                url="https://spokeo.com/john-doe", found=False, status="not_found")
    base.update(kw)
    return BrokerScanResult(**base)


_REMOVAL = {
    "id": 1, "broker_slug": "spokeo", "broker_name": "Spokeo",
    "person_first_name": "John", "person_last_name": "Doe",
    "search_url_pattern": "https://spokeo.com/{first}-{last}", "attempts": 0,
}


@pytest.mark.asyncio
@patch("digital_footprint.removers.verification.scan_broker")
async def test_verify_confirmed(mock_scan):
    mock_scan.return_value = _result(found=False, status="not_found")
    result = await RemovalVerifier().verify_single(dict(_REMOVAL))
    assert result["status"] == "confirmed"


@pytest.mark.asyncio
@patch("digital_footprint.removers.verification.scan_broker")
async def test_verify_still_found(mock_scan):
    mock_scan.return_value = _result(found=True, status="found")
    result = await RemovalVerifier().verify_single({**_REMOVAL, "attempts": 1})
    assert result["status"] == "still_found"
    assert result["attempts"] == 2


@pytest.mark.asyncio
@patch("digital_footprint.removers.verification.scan_broker")
async def test_verify_max_attempts_reached(mock_scan):
    mock_scan.return_value = _result(found=True, status="found")
    result = await RemovalVerifier().verify_single({**_REMOVAL, "attempts": 3})
    assert result["status"] == "failed"


@pytest.mark.asyncio
@patch("digital_footprint.removers.verification.scan_broker")
async def test_verify_scan_error_is_unverifiable(mock_scan):
    # A scan error must NOT be reported as 'confirmed' (that was the old
    # false-all-clear bug). The honest result is unverifiable.
    mock_scan.return_value = _result(found=False, status="error", error="Timeout")
    result = await RemovalVerifier().verify_single(dict(_REMOVAL))
    assert result["status"] == "unverifiable"


@pytest.mark.asyncio
@patch("digital_footprint.removers.verification.scan_broker")
async def test_verify_blocked_is_unverifiable(mock_scan):
    # An anti-bot challenge tells us nothing about listing status.
    mock_scan.return_value = _result(found=False, status="blocked", blocked=True)
    result = await RemovalVerifier().verify_single(dict(_REMOVAL))
    assert result["status"] == "unverifiable"
