"""Tests for username scanner (Maigret wrapper)."""

import json
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

from digital_footprint.scanners.username_scanner import (
    search_username,
    parse_maigret_results,
    UsernameResult,
)


@pytest.fixture
def maigret_json_output():
    """Maigret simple JSON format: flat dict of site_name -> info."""
    return {
        "GitHub": {
            "url_user": "https://github.com/testuser",
            "status": {
                "username": "testuser",
                "site_name": "GitHub",
                "url": "https://github.com/testuser",
                "status": "Claimed",
                "tags": ["coding"],
            },
        },
        "Twitter": {
            "url_user": "https://twitter.com/testuser",
            "status": {
                "username": "testuser",
                "site_name": "Twitter",
                "url": "https://twitter.com/testuser",
                "status": "Claimed",
                "tags": ["social"],
            },
        },
        "Reddit": {
            "url_user": "https://reddit.com/user/testuser",
            "status": {
                "username": "testuser",
                "site_name": "Reddit",
                "url": "https://reddit.com/user/testuser",
                "status": "Claimed",
                "tags": ["social"],
            },
        },
        "Instagram": {
            "url_user": "https://instagram.com/testuser",
            "status": {
                "username": "testuser",
                "site_name": "Instagram",
                "url": "https://instagram.com/testuser",
                "status": "Available",
                "tags": ["social"],
            },
        },
    }


def test_parse_maigret_results(maigret_json_output):
    results = parse_maigret_results(maigret_json_output)
    assert len(results) == 3  # Only "Claimed" entries
    assert all(isinstance(r, UsernameResult) for r in results)
    sites = {r.site_name for r in results}
    assert "GitHub" in sites
    assert "Twitter" in sites
    assert "Instagram" not in sites  # Available, not Claimed


def test_parse_maigret_results_empty():
    results = parse_maigret_results({})
    assert results == []


def test_username_result_risk_level():
    social = UsernameResult(site_name="Twitter", url="https://twitter.com/u", tags=["social"])
    assert social.risk_level == "medium"

    coding = UsernameResult(site_name="GitHub", url="https://github.com/u", tags=["coding"])
    assert coding.risk_level == "low"

    dating = UsernameResult(site_name="AFF", url="https://example.com", tags=["dating"])
    assert dating.risk_level == "high"


@pytest.mark.asyncio
async def test_search_username_runs_maigret(tmp_path, maigret_json_output):
    output_file = tmp_path / "report_testuser_simple.json"
    output_file.write_text(json.dumps(maigret_json_output))

    mock_proc = MagicMock()
    mock_proc.returncode = 0

    with patch("digital_footprint.scanners.username_scanner.asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = mock_proc
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("digital_footprint.scanners.username_scanner._get_output_dir", return_value=tmp_path):
            results = await search_username("testuser")

    assert len(results) == 3
    sites = {r.site_name for r in results}
    assert "GitHub" in sites
