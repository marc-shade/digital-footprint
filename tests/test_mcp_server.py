"""End-to-end MCP server verification (P1-7).

Drives the FastMCP server through the real in-process MCP client
(fastmcp.Client) — tool discovery + dispatch over the protocol layer, not just
the underlying functions. The server binds its DB at import time, so we point
it at a temp DB via env BEFORE importing it.

Network / API-key tools (scan, breach_check, username_search,
dark_web_monitor, broker_check, broker_remove, protect, social_audit) are
verified as REGISTERED but not called live here.
"""

import os
import tempfile
from pathlib import Path

import pytest

os.environ["DIGITAL_FOOTPRINT_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "mcp_test.db")

import server  # noqa: E402  (must follow the env assignment; binds db at import)

# server.db is now bound to the temp DB; drop the env var so it does not leak
# into other test modules (e.g. test_config's default-path assertion).
os.environ.pop("DIGITAL_FOOTPRINT_DB_PATH", None)

from fastmcp import Client  # noqa: E402

EXPECTED_TOOLS = {
    "footprint_add_person", "footprint_list_persons", "footprint_get_person",
    "footprint_update_person", "footprint_list_brokers", "footprint_get_broker",
    "footprint_broker_stats", "footprint_status", "footprint_scan",
    "footprint_breach_check", "footprint_username_search", "footprint_exposure_report",
    "footprint_google_dork", "footprint_broker_check", "footprint_broker_remove",
    "footprint_removal_status", "footprint_verify_removals", "footprint_dark_web_monitor",
    "footprint_social_audit", "footprint_schedule_status", "footprint_protect",
}


def _text(result) -> str:
    if getattr(result, "content", None):
        return "".join(getattr(c, "text", "") for c in result.content)
    return ""


@pytest.mark.asyncio
async def test_all_tools_registered_over_mcp():
    async with Client(server.mcp) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
    assert names == EXPECTED_TOOLS, f"tool set drift: {names ^ EXPECTED_TOOLS}"


@pytest.mark.asyncio
async def test_offline_tools_dispatch_over_mcp():
    async with Client(server.mcp) as client:
        # add a person via the MCP tool (id 1 in the fresh temp DB)
        added = await client.call_tool(
            "footprint_add_person", {"name": "MCP Test", "emails": ["mcp@example.com"]}
        )
        assert "MCP Test" in _text(added)

        # every offline-safe tool must dispatch and return a non-empty result
        offline = [
            ("footprint_status", {}),
            ("footprint_schedule_status", {}),
            ("footprint_list_brokers", {}),
            ("footprint_broker_stats", {}),
            ("footprint_get_broker", {"slug": "radaris"}),
            ("footprint_list_persons", {}),
            ("footprint_get_person", {"person_id": 1}),
            ("footprint_update_person", {"person_id": 1, "emails": ["mcp2@example.com"]}),
            ("footprint_google_dork", {"name": "MCP Test"}),
            ("footprint_exposure_report", {"person_id": 1}),
            ("footprint_removal_status", {"person_id": 1}),
            ("footprint_verify_removals", {"person_id": 1}),
        ]
        for name, args in offline:
            result = await client.call_tool(name, args)
            assert _text(result), f"{name} returned an empty result over MCP"

        # spot-check that dispatch reached the real implementation
        brokers = _text(await client.call_tool("footprint_list_brokers", {}))
        assert "radaris" in brokers.lower()
        person = _text(await client.call_tool("footprint_get_person", {"person_id": 1}))
        assert "mcp2@example.com" in person  # the update took effect
