"""Multi-format rendering of the exposure report (markdown / json / html / pdf).

Markdown is the canonical layout (exposure_report.generate_exposure_report).
This module adds a structured data model plus JSON, HTML and PDF renderers.

PDF uses fpdf2 (pure-Python) rather than WeasyPrint, whose native libs do not
install cleanly on this platform — the same reasoning that ruled out SQLCipher.
"""

import html as _html
import json
from datetime import datetime
from typing import Union

from digital_footprint.reporters.exposure_report import (
    compute_risk_score,
    risk_label,
    generate_exposure_report,
)

VALID_FORMATS = ("markdown", "md", "json", "html", "pdf")


def build_report_data(
    person_name: str,
    broker_results: list[dict],
    breach_results: dict,
    username_results: list[dict],
    dork_results: list[dict],
) -> dict:
    """Structured exposure report (the source for json/html/pdf rendering)."""
    hibp = breach_results.get("hibp_breaches", [])
    dehashed = breach_results.get("dehashed_records", [])

    all_findings: list[dict] = []
    for b in broker_results:
        if b.get("found"):
            all_findings.append(b)
    for x in hibp:
        all_findings.append({"risk_level": x.get("severity", "medium")})
    for x in dehashed:
        all_findings.append({"risk_level": x.get("severity", "medium")})
    all_findings.extend(username_results)
    all_findings.extend(dork_results)
    score = compute_risk_score(all_findings)

    brokers = [
        {"name": b.get("broker_name") or b.get("broker_slug") or "Unknown broker",
         "url": b.get("url", "")}
        for b in broker_results if b.get("found")
    ]
    breaches = [
        {"name": b.get("name") or b.get("breach_name") or "Unknown breach",
         "date": b.get("breach_date", ""),
         "data_classes": b.get("data_classes") or b.get("data_types") or []}
        for b in hibp
    ] + [
        {"name": r.get("database_name", "Unknown"), "date": "", "data_classes": []}
        for r in dehashed
    ]
    accounts = [
        {"site": u.get("site_name") or u.get("site") or "Unknown site", "url": u.get("url", "")}
        for u in username_results
    ]
    google = [{"title": d.get("title", "Link"), "url": d.get("url", "")} for d in dork_results]

    recs = []
    if brokers:
        recs.append("Submit opt-out requests to all detected data brokers.")
    if hibp:
        recs.append("Change passwords for all breached accounts and enable 2FA.")
    if accounts:
        recs.append("Review privacy settings on discovered accounts.")
    if not all_findings:
        recs.append("Your digital footprint appears minimal. Continue monitoring.")

    return {
        "subject": person_name,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "risk_score": score,
        "risk_label": risk_label(score),
        "brokers": brokers,
        "breaches": breaches,
        "breach_checked": breach_results.get("checked", True),
        "breach_errors": breach_results.get("errors", []),
        "accounts": accounts,
        "google_exposure": google,
        "recommendations": recs,
    }


def render_json(data: dict) -> str:
    return json.dumps(data, indent=2)


def render_html(data: dict) -> str:
    e = _html.escape

    def links(items, name_key, url_key):
        if not items:
            return "<li class='none'>None found.</li>"
        out = []
        for it in items:
            name = e(str(it.get(name_key, "")))
            url = it.get(url_key, "")
            extra = f" &mdash; <a href=\"{e(url)}\">{e(url)}</a>" if url else ""
            out.append(f"<li>{name}{extra}</li>")
        return "\n".join(out)

    def breach_items(items):
        if not items:
            if data.get("breach_checked", True):
                return "<li class='none'>No breach records found.</li>"
            errs = "; ".join(e(str(x)) for x in data.get("breach_errors", []))
            detail = f" ({errs})" if errs else ""
            return (f"<li class='warn'><strong>Breach check could not be completed{detail}.</strong> "
                    "This is NOT an all-clear — configure a valid HIBP API key and re-run.</li>")
        out = []
        for b in items:
            classes = ", ".join(e(str(c)) for c in b.get("data_classes", []))
            date = e(str(b.get("date") or "unknown"))
            out.append(f"<li><strong>{e(str(b.get('name', '')))}</strong> ({date}): {classes}</li>")
        return "\n".join(out)

    recs = "\n".join(f"<li>{e(r)}</li>" for r in data.get("recommendations", [])) or "<li class='none'>None.</li>"
    label = data["risk_label"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Exposure Report - {e(data['subject'])}</title>
<style>
 body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 760px;
   margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; line-height: 1.5; }}
 h1 {{ font-size: 1.6rem; margin-bottom: 0; }}
 .meta {{ color: #666; font-size: .9rem; }}
 .score {{ display: inline-block; padding: .3rem .7rem; border-radius: 6px;
   font-weight: 700; color: #fff; margin: .6rem 0; }}
 .CRITICAL {{ background: #b00020; }} .HIGH {{ background: #d9631a; }}
 .MODERATE {{ background: #b58900; }} .LOW {{ background: #2e7d32; }}
 h2 {{ font-size: 1.15rem; border-bottom: 1px solid #eee; padding-bottom: .2rem; margin-top: 1.6rem; }}
 ul {{ padding-left: 1.2rem; }} li.none {{ color: #888; list-style: none; margin-left: -1.2rem; }}
 li.warn {{ color: #b00020; list-style: none; margin-left: -1.2rem; }}
 a {{ color: #1a6fb5; word-break: break-all; }}
</style></head><body>
<h1>Digital Footprint Exposure Report</h1>
<p class="meta"><strong>Subject:</strong> {e(data['subject'])}<br>
<strong>Generated:</strong> {e(data['generated_at'])}</p>
<div class="score {label}">Risk score: {data['risk_score']}/100 ({label})</div>
<h2>Data Broker Exposure ({len(data['brokers'])} found)</h2>
<ul>{links(data['brokers'], 'name', 'url')}</ul>
<h2>Data Breaches ({len(data['breaches'])})</h2>
<ul>{breach_items(data['breaches'])}</ul>
<h2>Online Accounts ({len(data['accounts'])})</h2>
<ul>{links(data['accounts'], 'site', 'url')}</ul>
<h2>Google Exposure ({len(data['google_exposure'])})</h2>
<ul>{links(data['google_exposure'], 'title', 'url')}</ul>
<h2>Recommendations</h2>
<ul>{recs}</ul>
</body></html>"""


def _pdf_safe(text: str) -> str:
    # fpdf2 core fonts are latin-1; replace anything outside it so a name with
    # an accent or emoji never crashes PDF generation.
    return str(text).encode("latin-1", "replace").decode("latin-1")


def render_pdf(data: dict) -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _pdf_safe("Digital Footprint Exposure Report"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _pdf_safe(f"Subject: {data['subject']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _pdf_safe(f"Generated: {data['generated_at']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, _pdf_safe(f"Risk score: {data['risk_score']}/100 ({data['risk_label']})"),
             new_x="LMARGIN", new_y="NEXT")

    def section(title, lines):
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, _pdf_safe(title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        if not lines:
            pdf.cell(0, 6, _pdf_safe("  None found."), new_x="LMARGIN", new_y="NEXT")
            return
        for line in lines:
            # new_x=LMARGIN resets the cursor to the left margin after each
            # wrapped line; without it multi_cell leaves x at the right margin
            # and the next line has zero width ("no horizontal space").
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 6, _pdf_safe("- " + line), new_x="LMARGIN", new_y="NEXT")

    section(f"Data Broker Exposure ({len(data['brokers'])} found)",
            [f"{b['name']}: {b['url']}" for b in data["brokers"]])
    breach_lines = [f"{b['name']} ({b.get('date') or 'unknown'}): {', '.join(b.get('data_classes', []))}"
                    for b in data["breaches"]]
    if not breach_lines and not data.get("breach_checked", True):
        errs = "; ".join(str(x) for x in data.get("breach_errors", []))
        detail = f" ({errs})" if errs else ""
        breach_lines = [f"Breach check could not be completed{detail}. NOT an all-clear; "
                        "configure a valid HIBP API key and re-run."]
    section(f"Data Breaches ({len(data['breaches'])})", breach_lines)
    section(f"Online Accounts ({len(data['accounts'])})",
            [f"{a['site']}: {a['url']}" for a in data["accounts"]])
    section(f"Google Exposure ({len(data['google_exposure'])})",
            [f"{g['title']}: {g['url']}" for g in data["google_exposure"]])
    section("Recommendations", list(data.get("recommendations", [])))

    return bytes(pdf.output())


def render_report(
    person_name: str,
    broker_results: list[dict],
    breach_results: dict,
    username_results: list[dict],
    dork_results: list[dict],
    fmt: str = "markdown",
) -> Union[str, bytes]:
    """Render the exposure report in the requested format. Returns str for
    markdown/json/html, bytes for pdf."""
    fmt = (fmt or "markdown").lower()
    if fmt in ("markdown", "md"):
        return generate_exposure_report(person_name, broker_results, breach_results, username_results, dork_results)
    data = build_report_data(person_name, broker_results, breach_results, username_results, dork_results)
    if fmt == "json":
        return render_json(data)
    if fmt == "html":
        return render_html(data)
    if fmt == "pdf":
        return render_pdf(data)
    raise ValueError(f"unknown report format: {fmt!r}. valid: {', '.join(VALID_FORMATS)}")
