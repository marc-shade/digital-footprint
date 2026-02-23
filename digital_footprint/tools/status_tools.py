"""System status MCP tools."""

from digital_footprint.db import Database


def register_status_tools(mcp, db: Database):
    """Register status dashboard tool."""

    @mcp.tool()
    def footprint_status() -> str:
        """Get Digital Footprint system status dashboard.

        Shows protection overview: persons, brokers, findings, removals, breaches, and last scan.
        """
        s = db.get_status()
        lines = [
            "=== Digital Footprint Status ===",
            "",
            f"Protected persons: {s['persons_count']}",
            f"Broker registry:   {s['brokers_count']} brokers",
            "",
            "Findings:",
            f"  Active:           {s['findings']['active']}",
            f"  Removal pending:  {s['findings']['removal_pending']}",
            f"  Removed:          {s['findings']['removed']}",
            "",
            "Removals:",
            f"  Pending:          {s['removals']['pending']}",
            f"  Submitted:        {s['removals']['submitted']}",
            f"  Confirmed:        {s['removals']['confirmed']}",
            "",
            f"Breaches detected:  {s['breaches_count']}",
            f"Last scan:          {s['last_scan'] or 'never'}",
        ]
        return "\n".join(lines)
