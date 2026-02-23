"""Email registration scanner using holehe CLI."""

import asyncio
from dataclasses import dataclass


HIGH_RISK_CATEGORIES = {"dating", "adult", "financial", "gambling"}
MEDIUM_RISK_CATEGORIES = {"social", "photo", "video", "gaming", "forum"}


@dataclass
class HoleheResult:
    service: str
    exists: bool
    category: str = "other"

    @property
    def risk_level(self) -> str:
        if self.category in HIGH_RISK_CATEGORIES:
            return "high"
        if self.category in MEDIUM_RISK_CATEGORIES:
            return "medium"
        return "low"


def parse_holehe_output(stdout: str) -> list[HoleheResult]:
    """Parse holehe CSV-style stdout output."""
    results = []
    for line in stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.strip().split(",")
        if len(parts) < 2:
            continue
        service = parts[0].strip()
        status = parts[1].strip()
        category = parts[2].strip() if len(parts) > 2 else "other"
        if status == "Used":
            results.append(HoleheResult(
                service=service,
                exists=True,
                category=category,
            ))
    return results


async def check_email_registrations(
    email: str, timeout: int = 60
) -> list[HoleheResult]:
    """Check which services an email is registered with using holehe.

    Note: Uses create_subprocess_exec (not shell) for safety - arguments
    are passed as a list, preventing shell injection.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "holehe", email,
            "--only-used", "--csv",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return parse_holehe_output(stdout.decode())
    except FileNotFoundError:
        return []
    except Exception:
        return []
