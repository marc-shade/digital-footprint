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
    assert data["first_name"] == "John"
    assert data["last_name"] == "Doe"


def test_build_form_data_with_lists():
    remover = WebFormRemover()
    person = {
        "name": "John Doe",
        "emails": ["john@example.com", "john2@example.com"],
        "phones": ["555-1234"],
        "addresses": ["123 Main St"],
    }
    broker = {"opt_out_url": "https://broker.com/optout"}
    data = remover.build_form_data(person, broker)
    assert data["email"] == "john@example.com"
    assert data["phone"] == "555-1234"
    assert data["address"] == "123 Main St"


@pytest.mark.asyncio
@patch("digital_footprint.removers.web_form_remover.create_stealth_browser")
async def test_submit_fills_form_and_submits(mock_browser):
    mock_locator = AsyncMock()
    mock_locator.count = AsyncMock(return_value=1)
    mock_locator.is_visible = AsyncMock(return_value=True)
    mock_locator.click = AsyncMock()
    mock_locator.fill = AsyncMock()

    mock_page = AsyncMock()
    mock_page.content = AsyncMock(return_value="<div><input name='email'><button type='submit'>Submit</button></div>")
    mock_page.inner_text = AsyncMock(return_value="Your request has been submitted")
    mock_page.locator = MagicMock(return_value=MagicMock(first=mock_locator))

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_pw = AsyncMock()
    mock_brow = AsyncMock()
    mock_browser.return_value = (mock_pw, mock_brow, mock_context)

    remover = WebFormRemover()
    with patch("digital_footprint.removers.web_form_remover.random_delay", new_callable=AsyncMock):
        result = await remover.submit(
            person={"name": "John Doe", "email": "john@example.com"},
            broker={
                "name": "TestBroker",
                "opt_out_url": "https://testbroker.com/optout",
            },
        )

    assert result["status"] == "submitted"
    assert result["form_submitted"] is True
    assert result["fields_filled"] > 0
    mock_page.goto.assert_called_once_with("https://testbroker.com/optout", timeout=30000)


@pytest.mark.asyncio
@patch("digital_footprint.removers.web_form_remover.create_stealth_browser")
async def test_submit_captcha_detected(mock_browser):
    mock_page = AsyncMock()
    mock_page.content = AsyncMock(return_value='<div class="g-recaptcha">captcha here</div>')

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_pw = AsyncMock()
    mock_brow = AsyncMock()
    mock_browser.return_value = (mock_pw, mock_brow, mock_context)

    remover = WebFormRemover()
    result = await remover.submit(
        person={"name": "John Doe", "email": "john@example.com"},
        broker={"name": "TestBroker", "opt_out_url": "https://testbroker.com/optout"},
    )

    assert result["status"] == "captcha_required"


@pytest.mark.asyncio
async def test_submit_no_optout_url():
    remover = WebFormRemover()
    result = await remover.submit(
        person={"name": "John Doe", "email": "john@example.com"},
        broker={"name": "TestBroker"},
    )
    assert result["status"] == "error"
    assert "opt-out URL" in result["message"]


@pytest.mark.asyncio
@patch("digital_footprint.removers.web_form_remover.create_stealth_browser")
async def test_submit_no_form_fields(mock_browser):
    mock_locator = AsyncMock()
    mock_locator.count = AsyncMock(return_value=0)

    mock_page = AsyncMock()
    mock_page.content = AsyncMock(return_value="<div>No form here</div>")
    mock_page.inner_text = AsyncMock(return_value="This page has no form")
    mock_page.locator = MagicMock(return_value=MagicMock(first=mock_locator))

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_pw = AsyncMock()
    mock_brow = AsyncMock()
    mock_browser.return_value = (mock_pw, mock_brow, mock_context)

    remover = WebFormRemover()
    with patch("digital_footprint.removers.web_form_remover.random_delay", new_callable=AsyncMock):
        result = await remover.submit(
            person={"name": "John Doe", "email": "john@example.com"},
            broker={"name": "TestBroker", "opt_out_url": "https://testbroker.com/optout"},
        )

    assert result["status"] == "no_form_found"
