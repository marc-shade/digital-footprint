"""Tests for holehe email registration scanner."""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock
from digital_footprint.scanners.holehe_scanner import (
    HoleheResult,
    parse_holehe_output,
    check_email_registrations,
)


def test_parse_holehe_output_legacy_format():
    stdout = "twitter.com,Used,social\ninstagram.com,Used,social\nnetflix.com,Used,streaming\nadobe.com,Used,software\ndating-site.com,Used,dating\nunknown.com,Not Used,other\n"
    results = parse_holehe_output(stdout)
    assert len(results) == 5
    assert results[0].service == "twitter.com"
    assert results[0].exists is True


def test_parse_holehe_output_csv_format():
    """Parse holehe's actual CSV file format with header."""
    csv = "Name,Domain,Exists,Rate Limit,Others\nTwitter,twitter.com,True,False,\nInstagram,instagram.com,True,False,\nNetflix,netflix.com,False,False,\n"
    results = parse_holehe_output(csv)
    assert len(results) == 2
    assert results[0].service == "twitter.com"
    assert results[1].service == "instagram.com"


def test_parse_holehe_output_empty():
    results = parse_holehe_output("")
    assert results == []


def test_holehe_result_risk_level_high():
    r = HoleheResult(service="dating-site.com", exists=True, category="dating")
    assert r.risk_level == "high"


def test_holehe_result_risk_level_medium():
    r = HoleheResult(service="twitter.com", exists=True, category="social")
    assert r.risk_level == "medium"


def test_holehe_result_risk_level_low():
    r = HoleheResult(service="netflix.com", exists=True, category="streaming")
    assert r.risk_level == "low"


@pytest.mark.asyncio
@patch("digital_footprint.scanners.holehe_scanner.asyncio.create_subprocess_exec")
async def test_check_email_registrations(mock_exec, tmp_path):
    csv_file = tmp_path / "holehe_test.csv"
    csv_file.write_text("twitter.com,Used,social\ninstagram.com,Used,social\n")

    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"", b"")
    mock_proc.returncode = 0
    mock_exec.return_value = mock_proc

    with patch("digital_footprint.scanners.holehe_scanner.tempfile.mktemp", return_value=str(csv_file)):
        results = await check_email_registrations("test@example.com")

    assert len(results) == 2
    assert results[0].service == "twitter.com"


@pytest.mark.asyncio
@patch("digital_footprint.scanners.holehe_scanner.asyncio.create_subprocess_exec")
async def test_check_email_registrations_holehe_not_installed(mock_exec):
    mock_exec.side_effect = FileNotFoundError("holehe not found")
    results = await check_email_registrations("test@example.com")
    assert results == []


@pytest.mark.asyncio
@patch("digital_footprint.scanners.holehe_scanner.asyncio.wait_for", side_effect=asyncio.TimeoutError)
@patch("digital_footprint.scanners.holehe_scanner.asyncio.create_subprocess_exec")
async def test_check_email_registrations_timeout(mock_exec, mock_wait_for):
    mock_proc = AsyncMock()
    mock_proc.kill = lambda: None
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))
    mock_exec.return_value = mock_proc

    results = await check_email_registrations("test@example.com", timeout=1)
    assert results == []
