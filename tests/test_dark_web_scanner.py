"""Tests for dark web scanner (HIBP pastes + Ahmia.fi)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from digital_footprint.scanners.dark_web_scanner import (
    PasteResult,
    AhmiaResult,
    check_hibp_pastes,
    search_ahmia,
)


@pytest.mark.asyncio
async def test_check_hibp_pastes_found():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {
            "Source": "Pastebin",
            "Id": "abc123",
            "Title": "Leaked emails dump",
            "Date": "2024-01-15T00:00:00Z",
            "EmailCount": 500,
        },
        {
            "Source": "Ghostbin",
            "Id": "def456",
            "Title": None,
            "Date": "2023-06-01T00:00:00Z",
            "EmailCount": 100,
        },
    ]

    with patch("digital_footprint.scanners.dark_web_scanner.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        results = await check_hibp_pastes("test@example.com", api_key="test-key")

    assert len(results) == 2
    assert results[0].source == "Pastebin"
    assert results[0].title == "Leaked emails dump"
    assert results[0].severity == "high"


@pytest.mark.asyncio
async def test_check_hibp_pastes_not_found():
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("digital_footprint.scanners.dark_web_scanner.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        results = await check_hibp_pastes("clean@example.com", api_key="test-key")

    assert results == []


@pytest.mark.asyncio
async def test_check_hibp_pastes_no_key():
    results = await check_hibp_pastes("test@example.com", api_key="")
    assert results == []


def test_paste_result_severity():
    r = PasteResult(source="Pastebin", paste_id="abc", title="dump", date="2024-01-01", email_count=500)
    assert r.severity == "high"


@pytest.mark.asyncio
async def test_search_ahmia_found():
    html = """
    <html><body>
    <li class="result">
      <h4><a href="http://example.onion/page1">Leaked Database Dump</a></h4>
      <p>Contains email addresses and passwords...</p>
      <cite>http://example.onion/page1</cite>
    </li>
    <li class="result">
      <h4><a href="http://example2.onion/data">Data Collection</a></h4>
      <p>Email list compilation</p>
      <cite>http://example2.onion/data</cite>
    </li>
    </body></html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html

    with patch("digital_footprint.scanners.dark_web_scanner.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        results = await search_ahmia("test@example.com")

    assert len(results) == 2
    assert results[0].title == "Leaked Database Dump"
    assert results[0].url == "http://example.onion/page1"


@pytest.mark.asyncio
async def test_search_ahmia_no_results():
    html = "<html><body><p>No results found</p></body></html>"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html

    with patch("digital_footprint.scanners.dark_web_scanner.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        results = await search_ahmia("clean@example.com")

    assert results == []
