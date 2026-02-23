"""Tests for breach scanner (HIBP + DeHashed)."""

import json
from unittest.mock import AsyncMock, patch, MagicMock
import pytest

from digital_footprint.scanners.breach_scanner import (
    check_hibp,
    check_dehashed,
    scan_breaches,
    HibpBreach,
    DehashedRecord,
)


@pytest.fixture
def hibp_response():
    return [
        {
            "Name": "LinkedIn",
            "Title": "LinkedIn",
            "Domain": "linkedin.com",
            "BreachDate": "2012-05-05",
            "DataClasses": ["Email addresses", "Passwords"],
            "IsVerified": True,
        },
        {
            "Name": "Adobe",
            "Title": "Adobe",
            "Domain": "adobe.com",
            "BreachDate": "2013-10-04",
            "DataClasses": ["Email addresses", "Password hints", "Passwords", "Usernames"],
            "IsVerified": True,
        },
    ]


@pytest.fixture
def dehashed_response():
    return {
        "total": 1,
        "entries": [
            {
                "email": "test@example.com",
                "username": "testuser",
                "password": "hashed123",
                "hashed_password": "abc123hash",
                "name": "Test User",
                "database_name": "SomeDB",
            }
        ],
    }


@pytest.mark.asyncio
async def test_check_hibp_found(hibp_response):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = hibp_response

    with patch("digital_footprint.scanners.breach_scanner.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        results = await check_hibp("test@example.com", api_key="test-key")

    assert len(results) == 2
    assert isinstance(results[0], HibpBreach)
    assert results[0].name == "LinkedIn"
    assert results[0].breach_date == "2012-05-05"
    assert "Passwords" in results[0].data_classes


@pytest.mark.asyncio
async def test_check_hibp_not_found():
    mock_response = AsyncMock()
    mock_response.status_code = 404

    with patch("digital_footprint.scanners.breach_scanner.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        results = await check_hibp("clean@example.com", api_key="test-key")

    assert results == []


@pytest.mark.asyncio
async def test_check_hibp_no_api_key():
    results = await check_hibp("test@example.com", api_key=None)
    assert results == []


@pytest.mark.asyncio
async def test_check_dehashed_found(dehashed_response):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = dehashed_response

    with patch("digital_footprint.scanners.breach_scanner.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        results = await check_dehashed("test@example.com", api_key="test-key")

    assert len(results) == 1
    assert isinstance(results[0], DehashedRecord)
    assert results[0].email == "test@example.com"
    assert results[0].database_name == "SomeDB"


@pytest.mark.asyncio
async def test_check_dehashed_no_api_key():
    results = await check_dehashed("test@example.com", api_key=None)
    assert results == []


@pytest.mark.asyncio
async def test_scan_breaches_combines_sources(hibp_response, dehashed_response):
    mock_hibp_resp = MagicMock()
    mock_hibp_resp.status_code = 200
    mock_hibp_resp.json.return_value = hibp_response

    mock_dh_resp = MagicMock()
    mock_dh_resp.status_code = 200
    mock_dh_resp.json.return_value = dehashed_response

    with patch("digital_footprint.scanners.breach_scanner.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.side_effect = [mock_hibp_resp, mock_dh_resp]
        mock_client_cls.return_value = mock_client

        results = await scan_breaches(
            "test@example.com",
            hibp_api_key="test-key",
            dehashed_api_key="test-key",
        )

    assert results["hibp_count"] == 2
    assert results["dehashed_count"] == 1
    assert results["total"] == 3
