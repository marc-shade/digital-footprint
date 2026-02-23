"""Removal verification by re-scanning broker sites."""

from datetime import datetime

from digital_footprint.scanners.broker_scanner import scan_broker


MAX_ATTEMPTS = 3


class RemovalVerifier:
    async def verify_single(self, removal: dict) -> dict:
        broker_slug = removal["broker_slug"]
        broker_name = removal["broker_name"]
        first_name = removal["person_first_name"]
        last_name = removal["person_last_name"]
        url_pattern = removal.get("search_url_pattern", "")
        attempts = removal.get("attempts", 0)

        if not url_pattern:
            return {
                "removal_id": removal["id"],
                "status": "skipped",
                "reason": "No search URL pattern for broker",
            }

        result = await scan_broker(
            broker_slug=broker_slug,
            broker_name=broker_name,
            url_pattern=url_pattern,
            first_name=first_name,
            last_name=last_name,
        )

        if not result.found:
            return {
                "removal_id": removal["id"],
                "status": "confirmed",
                "verified_at": datetime.now().isoformat(),
            }

        new_attempts = attempts + 1
        if new_attempts > MAX_ATTEMPTS:
            return {
                "removal_id": removal["id"],
                "status": "failed",
                "attempts": new_attempts,
                "message": f"Still found on {broker_name} after {new_attempts} checks",
            }

        return {
            "removal_id": removal["id"],
            "status": "still_found",
            "attempts": new_attempts,
            "message": f"Still listed on {broker_name}. Will re-check.",
        }
