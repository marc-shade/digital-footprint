"""`python -m digital_footprint` — run the Digital Footprint MCP server.

The server module (top-level `server.py`) builds the FastMCP `mcp` object and
registers all tools at import time; we just start it here.
"""
from server import mcp


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
