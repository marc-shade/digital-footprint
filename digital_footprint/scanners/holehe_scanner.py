"""Email registration scanner using holehe CLI."""

import asyncio
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


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


def parse_holehe_output(text: str) -> list[HoleheResult]:
    """Parse holehe output (CSV file or legacy CSV stdout).

    Handles two formats:
    - Holehe CSV file: Name,Domain,Exists,Rate Limit,Others (with header)
    - Legacy format: service,Used,category
    """
    results = []
    lines = text.strip().split("\n")
    if not lines or not lines[0].strip():
        return results

    # Detect header row
    first = lines[0].lower().strip()
    start = 0
    if first.startswith("name") or first.startswith("service"):
        start = 1

    for line in lines[start:]:
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue

        # Holehe CSV: Name,Domain,Exists,Rate Limit,...
        if len(parts) >= 3 and parts[2].lower() in ("true", "false"):
            if parts[2].lower() == "true":
                service = parts[1] if parts[1] else parts[0]
                results.append(HoleheResult(service=service, exists=True))
        # Legacy: service,Used/Not Used,category
        elif parts[1].lower() in ("used", "not used"):
            if parts[1].lower() == "used":
                category = parts[2] if len(parts) > 2 else "other"
                results.append(HoleheResult(
                    service=parts[0],
                    exists=True,
                    category=category,
                ))

    return results


async def check_email_registrations(
    email: str, timeout: int = 60
) -> list[HoleheResult]:
    """Check which services an email is registered with using holehe.

    Holehe's --csv flag writes to a file, so we use a temp file and parse it.
    """
    csv_path = None
    try:
        csv_path = tempfile.mktemp(suffix=".csv", prefix="holehe_")
        proc = await asyncio.create_subprocess_exec(
            "holehe", email,
            "--only-used", "--csv", csv_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return []

        csv_file = Path(csv_path)
        if not csv_file.exists():
            return []

        csv_content = csv_file.read_text()
        return parse_holehe_output(csv_content)

    except FileNotFoundError:
        return []
    except Exception:
        return []
    finally:
        if csv_path:
            try:
                os.unlink(csv_path)
            except OSError:
                pass
