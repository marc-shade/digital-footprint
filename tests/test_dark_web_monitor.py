"""Tests for dark web monitoring orchestrator."""

import pytest
from unittest.mock import patch, AsyncMock
from digital_footprint.monitors.dark_web_monitor import run_dark_web_scan, format_dark_web_report


@pytest.mark.asyncio
@patch("digital_footprint.monitors.dark_web_monitor.check_email_registrations")
@patch("digital_footprint.monitors.dark_web_monitor.search_ahmia")
@patch("digital_footprint.monitors.dark_web_monitor.check_hibp_pastes")
async def test_run_dark_web_scan(mock_pastes, mock_ahmia, mock_holehe):
    from digital_footprint.scanners.dark_web_scanner import PasteResult, AhmiaResult
    from digital_footprint.scanners.holehe_scanner import HoleheResult

    mock_pastes.return_value = [PasteResult(source="Pastebin", paste_id="abc", title="Dump", date="2024-01-01")]
    mock_ahmia.return_value = [AhmiaResult(title="Leak Forum", url="http://example.onion/leak")]
    mock_holehe.return_value = [
        HoleheResult(service="twitter.com", exists=True, category="social"),
        HoleheResult(service="netflix.com", exists=True, category="streaming"),
    ]

    results = await run_dark_web_scan("test@example.com", hibp_api_key="key")
    assert results["paste_count"] == 1
    assert results["ahmia_count"] == 1
    assert results["holehe_count"] == 2
    assert results["total"] == 4


@pytest.mark.asyncio
@patch("digital_footprint.monitors.dark_web_monitor.check_email_registrations")
@patch("digital_footprint.monitors.dark_web_monitor.search_ahmia")
@patch("digital_footprint.monitors.dark_web_monitor.check_hibp_pastes")
async def test_run_dark_web_scan_no_results(mock_pastes, mock_ahmia, mock_holehe):
    mock_pastes.return_value = []
    mock_ahmia.return_value = []
    mock_holehe.return_value = []
    results = await run_dark_web_scan("clean@example.com", hibp_api_key="key")
    assert results["total"] == 0


def test_format_dark_web_report():
    results = {
        "email": "test@example.com",
        "paste_count": 1, "ahmia_count": 0, "holehe_count": 3, "total": 4,
        "pastes": [{"source": "Pastebin", "title": "Dump", "severity": "high"}],
        "ahmia_results": [],
        "holehe_results": [
            {"service": "twitter.com", "category": "social", "risk_level": "medium"},
            {"service": "netflix.com", "category": "streaming", "risk_level": "low"},
            {"service": "dating.com", "category": "dating", "risk_level": "high"},
        ],
    }
    report = format_dark_web_report(results)
    assert "test@example.com" in report
    assert "Pastebin" in report
    assert "twitter.com" in report
    assert "dating.com" in report
