"""Username scanner using Maigret."""

import asyncio
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class UsernameResult:
    site_name: str
    url: str
    tags: list[str] = field(default_factory=list)

    @property
    def risk_level(self) -> str:
        high_risk_tags = {"dating", "adult", "financial", "gambling"}
        if high_risk_tags & set(self.tags):
            return "high"
        medium_risk_tags = {"social", "photo", "video", "gaming", "forum"}
        if medium_risk_tags & set(self.tags):
            return "medium"
        return "low"


def _get_output_dir() -> Path:
    output_dir = Path(tempfile.gettempdir()) / "maigret_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def parse_maigret_results(data: dict) -> list[UsernameResult]:
    """Parse Maigret simple JSON output into UsernameResult objects.

    Maigret simple JSON is a flat dict: {site_name: {status: {status, tags, url}, url_user, ...}}
    """
    results = []
    for site_name, info in data.items():
        status_obj = info.get("status", {})
        if isinstance(status_obj, dict) and status_obj.get("status") == "Claimed":
            results.append(
                UsernameResult(
                    site_name=status_obj.get("site_name", site_name),
                    url=status_obj.get("url", info.get("url_user", "")),
                    tags=status_obj.get("tags", []),
                )
            )
    return results


async def search_username(
    username: str, timeout: int = 120
) -> list[UsernameResult]:
    """Search for a username across sites using Maigret."""
    output_dir = _get_output_dir()

    proc = await asyncio.create_subprocess_exec(
        "maigret", username,
        "-J", "simple",
        "--folderoutput", str(output_dir),
        "--timeout", str(timeout),
        "--no-color",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    # Maigret writes report_<username>_simple.json
    output_file = output_dir / f"report_{username}_simple.json"
    if not output_file.exists():
        return []

    data = json.loads(output_file.read_text())
    return parse_maigret_results(data)
