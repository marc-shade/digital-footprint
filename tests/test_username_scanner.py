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
    return {
        "testuser": {
            "GitHub": {
                "url_user": "https://github.com/testuser",
                "status": "Claimed",
                "tags": ["coding"],
            },
            "Twitter": {
                "url_user": "https://twitter.com/testuser",
                "status": "Claimed",
                "tags": ["social"],
            },
            "Reddit": {
                "url_user": "https://reddit.com/user/testuser",
                "status": "Claimed",
                "tags": ["social"],
            },
            "Instagram": {
                "url_user": "https://instagram.com/testuser",
                "status": "Available",
                "tags": ["social"],
            },
        }
    }


def test_parse_maigret_results(maigret_json_output):
    results = parse_maigret_results(maigret_json_output, "testuser")
    assert len(results) == 3  # Only "Claimed" entries
    assert all(isinstance(r, UsernameResult) for r in results)
    sites = {r.site_name for r in results}
    assert "GitHub" in sites
    assert "Twitter" in sites
    assert "Instagram" not in sites  # Available, not Claimed


def test_parse_maigret_results_empty():
    results = parse_maigret_results({}, "nobody")
    assert results == []


def test_username_result_risk_level():
    social = UsernameResult(site_name="Twitter", url="https://twitter.com/u", tags=["social"])
    assert social.risk_level == "medium"

    coding = UsernameResult(site_name="GitHub", url="https://github.com/u", tags=["coding"])
    assert coding.risk_level == "low"


@pytest.mark.asyncio
async def test_search_username_runs_maigret(tmp_path, maigret_json_output):
    output_file = tmp_path / "maigret_testuser.json"
    output_file.write_text(json.dumps(maigret_json_output))

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = ""
    mock_proc.stderr = ""

    with patch("digital_footprint.scanners.username_scanner.asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = mock_proc
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("digital_footprint.scanners.username_scanner._get_output_path", return_value=str(output_file)):
            results = await search_username("testuser")

    assert len(results) == 3
    assert results[0].site_name in {"GitHub", "Twitter", "Reddit"}
