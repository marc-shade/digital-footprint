"""Tests for Playwright-based broker scanner."""

from unittest.mock import AsyncMock, patch, MagicMock
import pytest

from digital_footprint.scanners.broker_scanner import (
    BrokerScanResult,
    build_search_url,
    check_name_in_results,
)
from digital_footprint.scanners.playwright_scanner import (
    create_stealth_browser,
)


def test_build_search_url_simple():
    url = build_search_url(
        url_pattern="https://spokeo.com/search?q={first}+{last}",
        first_name="John",
        last_name="Doe",
    )
    assert url == "https://spokeo.com/search?q=John+Doe"


def test_build_search_url_with_location():
    url = build_search_url(
        url_pattern="https://whitepages.com/name/{first}-{last}/{state}",
        first_name="John",
        last_name="Doe",
        state="CA",
    )
    assert url == "https://whitepages.com/name/John-Doe/CA"


def test_build_search_url_missing_optional():
    url = build_search_url(
        url_pattern="https://example.com/search?name={first}+{last}&city={city}",
        first_name="John",
        last_name="Doe",
    )
    assert url == "https://example.com/search?name=John+Doe&city="


def test_check_name_in_results_found():
    page_text = "Results for John Doe in San Francisco, CA. Age 35. Related: Jane Doe."
    assert check_name_in_results(page_text, "John", "Doe") is True


def test_check_name_in_results_not_found():
    page_text = "No results found for your search."
    assert check_name_in_results(page_text, "John", "Doe") is False


def test_check_name_in_results_partial_match():
    page_text = "John Smith found in records."
    assert check_name_in_results(page_text, "John", "Doe") is False


def test_broker_scan_result_properties():
    found = BrokerScanResult(
        broker_slug="spokeo",
        broker_name="Spokeo",
        url="https://spokeo.com/John-Doe",
        found=True,
        page_text="John Doe, age 35",
    )
    assert found.found is True
    assert found.risk_level == "high"

    not_found = BrokerScanResult(
        broker_slug="spokeo",
        broker_name="Spokeo",
        url="https://spokeo.com/John-Doe",
        found=False,
    )
    assert not_found.risk_level == "low"
