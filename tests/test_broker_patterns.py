"""Guard the verified search_url_pattern data (added 2026-07-17).

These patterns were verified against live sites with two common test names.
If one is removed or malformed, discovery silently stops working for that
broker, so pin them here.
"""

from pathlib import Path

from digital_footprint.broker_registry import load_all_brokers

BROKERS_DIR = Path(__file__).parent.parent / "digital_footprint" / "brokers"

# Brokers whose search_url_pattern was live-verified. Discovery depends on these.
VERIFIED = {"radaris", "thatsthem", "zabasearch", "addresses"}


def _by_slug():
    return {b.slug: b for b in load_all_brokers(BROKERS_DIR)}


def test_verified_brokers_have_patterns():
    brokers = _by_slug()
    for slug in VERIFIED:
        assert slug in brokers, f"broker {slug} missing"
        assert brokers[slug].search_url_pattern, f"{slug} lost its search_url_pattern"


def test_patterns_have_name_placeholders():
    for b in load_all_brokers(BROKERS_DIR):
        pat = b.search_url_pattern
        if pat:
            assert "{first}" in pat and "{last}" in pat, f"{b.slug} pattern missing placeholders: {pat}"


def test_pattern_count_matches_verified_set():
    # If someone adds a new pattern, they should extend VERIFIED (and verify it),
    # not slip an unverified one in silently.
    with_pat = {b.slug for b in load_all_brokers(BROKERS_DIR) if b.search_url_pattern}
    assert with_pat == VERIFIED, f"unexpected pattern set: {with_pat} vs {VERIFIED}"
