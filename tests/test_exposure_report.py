"""Tests for exposure report generator."""

import pytest

from digital_footprint.reporters.exposure_report import (
    compute_risk_score,
    risk_label,
    generate_exposure_report,
)


def test_compute_risk_score_empty():
    assert compute_risk_score([]) == 0


def test_compute_risk_score_single_critical():
    findings = [{"risk_level": "critical"}]
    assert compute_risk_score(findings) == 25


def test_compute_risk_score_mixed():
    findings = [
        {"risk_level": "critical"},
        {"risk_level": "high"},
        {"risk_level": "medium"},
        {"risk_level": "low"},
    ]
    assert compute_risk_score(findings) == 42  # 25 + 10 + 5 + 2


def test_compute_risk_score_capped_at_100():
    findings = [{"risk_level": "critical"}] * 10  # 250 uncapped
    assert compute_risk_score(findings) == 100


def test_risk_label_critical():
    assert risk_label(75) == "CRITICAL"
    assert risk_label(100) == "CRITICAL"


def test_risk_label_high():
    assert risk_label(50) == "HIGH"
    assert risk_label(74) == "HIGH"


def test_risk_label_moderate():
    assert risk_label(25) == "MODERATE"
    assert risk_label(49) == "MODERATE"


def test_risk_label_low():
    assert risk_label(0) == "LOW"
    assert risk_label(24) == "LOW"


def test_generate_exposure_report_empty():
    report = generate_exposure_report(
        person_name="John Doe",
        broker_results=[],
        breach_results={"hibp_breaches": [], "dehashed_records": [], "total": 0},
        username_results=[],
        dork_results=[],
    )
    assert "John Doe" in report
    assert "LOW" in report
    assert "Risk Score: 0/100" in report


def test_generate_exposure_report_with_findings():
    broker_results = [
        {"broker_name": "Spokeo", "found": True, "risk_level": "high", "url": "https://spokeo.com/john-doe"},
    ]
    breach_results = {
        "hibp_breaches": [
            {"name": "LinkedIn", "breach_date": "2012-05-05", "severity": "critical", "data_classes": ["Passwords"]},
        ],
        "dehashed_records": [],
        "total": 1,
    }
    username_results = [
        {"site_name": "GitHub", "url": "https://github.com/johndoe", "risk_level": "low"},
    ]

    report = generate_exposure_report(
        person_name="John Doe",
        broker_results=broker_results,
        breach_results=breach_results,
        username_results=username_results,
        dork_results=[],
    )
    assert "John Doe" in report
    assert "Spokeo" in report
    assert "LinkedIn" in report
    assert "GitHub" in report
    assert "Risk Score:" in report
