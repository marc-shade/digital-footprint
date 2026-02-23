"""Tests for web form removal handler."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from digital_footprint.removers.web_form_remover import WebFormRemover, detect_captcha


def test_detect_captcha_recaptcha():
    page_html = '<iframe src="https://www.google.com/recaptcha/api2/anchor"></iframe>'
    assert detect_captcha(page_html) is True


def test_detect_captcha_hcaptcha():
    page_html = '<div class="h-captcha" data-sitekey="xxx"></div>'
    assert detect_captcha(page_html) is True


def test_detect_captcha_none():
    page_html = "<div>Simple form</div>"
    assert detect_captcha(page_html) is False


def test_build_form_data():
    remover = WebFormRemover()
    person = {"name": "John Doe", "email": "john@example.com", "phone": "555-1234"}
    broker = {"opt_out_url": "https://broker.com/optout"}
    data = remover.build_form_data(person, broker)
    assert data["name"] == "John Doe"
    assert data["email"] == "john@example.com"


@pytest.mark.asyncio
@patch("digital_footprint.removers.web_form_remover.create_stealth_browser")
async def test_submit_navigates_to_optout_url(mock_browser):
    mock_page = AsyncMock()
    mock_page.content = AsyncMock(return_value="<div>Success</div>")
    mock_page.inner_text = AsyncMock(return_value="Your request has been submitted")

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_pw = AsyncMock()
    mock_brow = AsyncMock()
    mock_browser.return_value = (mock_pw, mock_brow, mock_context)

    remover = WebFormRemover()
    result = await remover.submit(
        person={"name": "John Doe", "email": "john@example.com"},
        broker={
            "name": "TestBroker",
            "opt_out_url": "https://testbroker.com/optout",
            "opt_out": {"steps": ["Navigate to opt-out page", "Submit the form"]},
        },
    )

    assert result["status"] == "submitted"
    mock_page.goto.assert_called_once_with("https://testbroker.com/optout", timeout=30000)


@pytest.mark.asyncio
async def test_submit_no_optout_url():
    remover = WebFormRemover()
    result = await remover.submit(
        person={"name": "John Doe", "email": "john@example.com"},
        broker={"name": "TestBroker"},
    )
    assert result["status"] == "error"
    assert "opt-out URL" in result["message"]
