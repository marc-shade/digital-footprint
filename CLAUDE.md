# Digital Footprint — CLAUDE.md

## Project Overview
Self-hosted personal data removal and privacy protection system. Replicates VanishID/DeleteMe/Incogni capabilities through MCP servers, Claude Code skills, and autonomous agents.

## Architecture
- **MCP Server**: `digital-footprint-mcp` (Python/FastMCP) — core tools for scanning, removal, monitoring
- **CLI**: `dfp` command (Python/Click) — quick access to all features
- **Skills**: `/footprint`, `/vanish`, `/exposure`, `/breach`, `/privacy-audit`
- **Agents**: orchestrator, broker-scanner, broker-remover, breach-monitor, osint-recon, exposure-reporter
- **Database**: SQLite at `~/.digital-footprint/footprint.db`
- **Broker Registry**: YAML files in `brokers/` directory

## Commands
```bash
python -m digital_footprint              # Run MCP server
python -m digital_footprint.cli scan     # CLI scan
python -m pytest tests/                  # Run tests
```

## Key Directories
```
src/digital_footprint/
  server.py              # MCP server entry
  cli.py                 # CLI entry (Click)
  db/                    # Database models and migrations
  scanners/              # Broker/OSINT/breach scanners
  removers/              # Per-broker removal automation
  monitors/              # Dark web and re-listing monitors
  reporters/             # Report generation
  templates/             # Email and legal templates
  utils/                 # Shared utilities
brokers/                 # YAML broker registry files
agents/                  # Claude Code agent definitions
skills/                  # Claude Code skill definitions
tests/                   # Test suite
```

## Conventions
- Python 3.11+, type hints throughout
- Playwright for browser automation (stealth mode)
- All PII encrypted at rest
- Rate limit all external requests
- YAML for broker definitions, Jinja2 for templates
- SQLite for state, enhanced-memory-mcp for cross-session knowledge
