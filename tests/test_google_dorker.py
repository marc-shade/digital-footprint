"""Tests for Google dorking scanner."""

import pytest

from digital_footprint.scanners.google_dorker import (
    build_dork_queries,
    DorkResult,
    parse_search_results,
)


def test_build_dork_queries_name_only():
    queries = build_dork_queries(name="John Doe")
    assert len(queries) >= 1
    assert any('"John Doe"' in q for q in queries)


def test_build_dork_queries_with_email():
    queries = build_dork_queries(name="John Doe", email="john@example.com")
    assert any('"john@example.com"' in q for q in queries)
    assert any("site:pastebin.com" in q for q in queries)


def test_build_dork_queries_with_phone():
    queries = build_dork_queries(name="John Doe", phone="555-0100")
    assert any('"555-0100"' in q for q in queries)


def test_build_dork_queries_with_all():
    queries = build_dork_queries(
        name="John Doe",
        email="john@example.com",
        phone="555-0100",
        address="123 Main St",
    )
    assert len(queries) >= 5


def test_dork_result_risk_level():
    paste = DorkResult(
        query="test", url="https://pastebin.com/abc", title="Paste", snippet="data"
    )
    assert paste.risk_level == "high"

    generic = DorkResult(
        query="test", url="https://example.com/page", title="Page", snippet="mention"
    )
    assert generic.risk_level == "medium"

    pdf = DorkResult(
        query="test", url="https://example.com/file.pdf", title="Doc", snippet="name"
    )
    assert pdf.risk_level == "high"


def test_parse_search_results():
    raw_results = [
        {"url": "https://example.com/page1", "title": "Result 1", "snippet": "Found data"},
        {"url": "https://example.com/page2", "title": "Result 2", "snippet": "More data"},
    ]
    results = parse_search_results(raw_results, query='"John Doe"')
    assert len(results) == 2
    assert all(isinstance(r, DorkResult) for r in results)
    assert results[0].query == '"John Doe"'
