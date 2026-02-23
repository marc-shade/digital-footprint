"""Tests for scan MCP tools."""

import json
from unittest.mock import patch, AsyncMock
import pytest

from digital_footprint.tools.scan_tools import (
    do_breach_check,
    do_exposure_report,
)


@pytest.mark.asyncio
async def test_do_breach_check_no_api_keys():
    result = await do_breach_check(email="test@example.com")
    parsed = json.loads(result)
    assert parsed["status"] == "no_api_keys"


@pytest.mark.asyncio
async def test_do_breach_check_with_hibp_key():
    mock_results = {
        "email": "test@example.com",
        "hibp_breaches": [],
        "hibp_count": 0,
        "dehashed_records": [],
        "dehashed_count": 0,
        "total": 0,
    }
    with patch("digital_footprint.tools.scan_tools.scan_breaches", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = mock_results
        result = await do_breach_check(email="test@example.com", hibp_api_key="key")

    parsed = json.loads(result)
    assert parsed["total"] == 0


def test_do_exposure_report_minimal(tmp_db):
    tmp_db.insert_person(name="John Doe", emails=["john@example.com"])
    report = do_exposure_report(person_id=1, db=tmp_db)
    assert "John Doe" in report
    assert "Risk Score" in report
