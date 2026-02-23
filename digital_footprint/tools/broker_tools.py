"""Broker registry MCP tools."""

import json
from typing import Optional

from digital_footprint.db import Database


def register_broker_tools(mcp, db: Database):
    """Register all broker-related tools with the MCP server."""

    @mcp.tool()
    def footprint_list_brokers(
        category: str = None,
        difficulty: str = None,
        automatable: bool = None,
    ) -> str:
        """List data brokers in the registry.

        Args:
            category: Filter by category (people_search, background_check, marketing, etc.)
            difficulty: Filter by difficulty (easy, medium, hard, manual)
            automatable: Filter by automation support (true/false)
        """
        brokers = db.list_brokers(category=category, difficulty=difficulty, automatable=automatable)
        if not brokers:
            return "No brokers match the filters."
        lines = []
        for b in brokers:
            auto = "auto" if b.automatable else "manual"
            lines.append(f"  {b.slug}: {b.name} [{b.category}] {b.difficulty}/{auto}")
        return f"{len(brokers)} brokers:\n" + "\n".join(lines)

    @mcp.tool()
    def footprint_get_broker(slug: str = None, name: str = None) -> str:
        """Get full details for a data broker including opt-out instructions.

        Args:
            slug: Broker slug (filename without .yaml)
            name: Broker name (fuzzy match)
        """
        if slug:
            broker = db.get_broker_by_slug(slug)
        elif name:
            all_brokers = db.list_brokers()
            broker = next((b for b in all_brokers if name.lower() in b.name.lower()), None)
        else:
            return "Provide either slug or name."
        if not broker:
            return "Broker not found."
        info = {
            "slug": broker.slug,
            "name": broker.name,
            "url": broker.url,
            "category": broker.category,
            "opt_out_method": broker.opt_out_method,
            "opt_out_url": broker.opt_out_url,
            "opt_out_email": broker.opt_out_email,
            "difficulty": broker.difficulty,
            "automatable": broker.automatable,
            "recheck_days": broker.recheck_days,
            "ccpa_compliant": broker.ccpa_compliant,
            "gdpr_compliant": broker.gdpr_compliant,
            "notes": broker.notes,
        }
        return json.dumps(info, indent=2)

    @mcp.tool()
    def footprint_broker_stats() -> str:
        """Get statistics about the broker registry."""
        stats = db.broker_stats()
        lines = [
            f"Total brokers: {stats['total']}",
            "",
            "By category:",
        ]
        for cat, count in sorted(stats["by_category"].items()):
            lines.append(f"  {cat}: {count}")
        lines.append("")
        lines.append("By difficulty:")
        for diff, count in sorted(stats["by_difficulty"].items()):
            lines.append(f"  {diff}: {count}")
        lines.append("")
        lines.append("By opt-out method:")
        for method, count in sorted(stats["by_method"].items()):
            lines.append(f"  {method}: {count}")
        lines.append("")
        lines.append(f"Automatable: {stats['automatable']}")
        return "\n".join(lines)
