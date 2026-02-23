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
        high_risk_tags = {"dating", "adult", "financial"}
        if high_risk_tags & set(self.tags):
            return "high"
        medium_risk_tags = {"social", "photo", "video"}
        if medium_risk_tags & set(self.tags):
            return "medium"
        return "low"


def _get_output_path(username: str) -> str:
    return str(Path(tempfile.gettempdir()) / f"maigret_{username}.json")


def parse_maigret_results(data: dict, username: str) -> list[UsernameResult]:
    """Parse Maigret JSON output into UsernameResult objects."""
    user_data = data.get(username, {})
    results = []
    for site_name, info in user_data.items():
        if info.get("status") == "Claimed":
            results.append(
                UsernameResult(
                    site_name=site_name,
                    url=info.get("url_user", ""),
                    tags=info.get("tags", []),
                )
            )
    return results


async def search_username(
    username: str, timeout: int = 120
) -> list[UsernameResult]:
    """Search for a username across sites using Maigret."""
    output_path = _get_output_path(username)

    proc = await asyncio.create_subprocess_exec(
        "maigret", username,
        "--json", output_path,
        "--timeout", str(timeout),
        "--no-color",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    output_file = Path(output_path)
    if not output_file.exists():
        return []

    data = json.loads(output_file.read_text())
    return parse_maigret_results(data, username)
