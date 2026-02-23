"""Tests for social media public profile auditor."""

import pytest
from unittest.mock import AsyncMock, patch
from digital_footprint.scanners.social_auditor import (
    SocialAuditResult,
    detect_platform,
    extract_meta_tags,
    compute_privacy_score,
    audit_profile,
    PLATFORM_SELECTORS,
)


def test_detect_platform_twitter():
    assert detect_platform("https://twitter.com/johndoe") == "twitter"
    assert detect_platform("https://x.com/johndoe") == "twitter"


def test_detect_platform_github():
    assert detect_platform("https://github.com/johndoe") == "github"


def test_detect_platform_instagram():
    assert detect_platform("https://instagram.com/johndoe") == "instagram"


def test_detect_platform_unknown():
    assert detect_platform("https://obscuresite.com/johndoe") == "unknown"


def test_extract_meta_tags():
    html = '<html><head><meta property="og:title" content="John Doe"><meta property="og:description" content="Developer in NYC. john@test.com"></head></html>'
    tags = extract_meta_tags(html)
    assert tags["og:title"] == "John Doe"
    assert "john@test.com" in tags["og:description"]


def test_compute_privacy_score_all_private():
    result = SocialAuditResult(platform="twitter", url="https://twitter.com/anon", visible_fields={}, pii_flags=[])
    assert compute_privacy_score(result) >= 80


def test_compute_privacy_score_exposed():
    result = SocialAuditResult(
        platform="twitter",
        url="https://twitter.com/johndoe",
        visible_fields={"name": "John Doe", "email": "john@test.com"},
        pii_flags=["email_visible", "phone_visible", "real_name_visible", "location_visible"],
    )
    score = compute_privacy_score(result)
    assert score <= 30


def test_platform_selectors_exist():
    assert "twitter" in PLATFORM_SELECTORS
    assert "github" in PLATFORM_SELECTORS
    assert "instagram" in PLATFORM_SELECTORS


@pytest.mark.asyncio
@patch("digital_footprint.scanners.social_auditor.create_stealth_browser")
async def test_audit_profile(mock_browser):
    mock_page = AsyncMock()
    mock_page.content = AsyncMock(return_value='<html><head><meta property="og:title" content="John Doe"><meta property="og:description" content="Software dev. john@test.com | 555-1234"></head><body><div>John Doe</div></body></html>')
    mock_page.inner_text = AsyncMock(return_value="John Doe\nSoftware developer in NYC\njohn@test.com")

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_pw = AsyncMock()
    mock_brow = AsyncMock()
    mock_browser.return_value = (mock_pw, mock_brow, mock_context)

    result = await audit_profile("https://twitter.com/johndoe")
    assert result.platform == "twitter"
    assert "email_visible" in result.pii_flags


@pytest.mark.asyncio
@patch("digital_footprint.scanners.social_auditor.create_stealth_browser")
async def test_audit_profile_error(mock_browser):
    mock_browser.side_effect = Exception("Browser launch failed")
    result = await audit_profile("https://twitter.com/johndoe")
    assert result.platform == "twitter"
    assert result.error is not None
