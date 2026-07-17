"""Tests for anti-bot challenge detection in the broker scanner.

A challenged/empty page must be reported as 'blocked', never as a real
'not_found' -- otherwise a blocked scan reads as a false all-clear.
"""

from digital_footprint.scanners.broker_scanner import detect_challenge, check_name_in_results


def test_cloudflare_interstitial_is_challenge():
    assert detect_challenge("Just a moment...", "Checking your browser before accessing")


def test_datadome_interstitial_is_challenge():
    # observed live on FastPeopleSearch
    assert detect_challenge("Luktelėkite...", "FastPeopleSearch Loading Search Results...")


def test_empty_body_is_challenge():
    # observed live on TruePeopleSearch (Cloudflare JS shell renders no text)
    assert detect_challenge("truepeoplesearch.com", "")


def test_real_results_page_is_not_challenge():
    body = "Search results for John Smith. 12 records found in Seattle, WA. " * 3
    assert not detect_challenge("John Smith - People Search", body)


def test_name_match_still_works_on_real_page():
    body = "Results: John Smith, age 42, Seattle WA"
    assert check_name_in_results(body, "John", "Smith")
    assert not check_name_in_results(body, "Jane", "Doe")
