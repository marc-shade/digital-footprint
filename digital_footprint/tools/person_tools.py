"""Person management MCP tools."""

import json
from typing import Optional

from digital_footprint.db import Database


def register_person_tools(mcp, db: Database):
    """Register all person-related tools with the MCP server."""

    @mcp.tool()
    def footprint_add_person(
        name: str,
        emails: list[str],
        phones: list[str] = None,
        addresses: list[str] = None,
        usernames: list[str] = None,
        date_of_birth: str = None,
        relation: str = "self",
    ) -> str:
        """Register a person for digital footprint protection.

        Args:
            name: Full legal name
            emails: Email addresses to monitor
            phones: Phone numbers (optional)
            addresses: Physical addresses (optional)
            usernames: Known usernames across platforms (optional)
            date_of_birth: Date of birth YYYY-MM-DD (optional)
            relation: Relationship - self, spouse, child, parent, other (default: self)
        """
        person_id = db.insert_person(
            name=name,
            emails=emails,
            phones=phones or [],
            addresses=addresses or [],
            usernames=usernames or [],
            relation=relation,
            date_of_birth=date_of_birth,
        )
        person = db.get_person(person_id)
        return json.dumps(person.to_dict(), indent=2)

    @mcp.tool()
    def footprint_list_persons() -> str:
        """List all persons currently under digital footprint protection."""
        persons = db.list_persons()
        if not persons:
            return "No persons registered. Use footprint_add_person to add someone."
        result = []
        for p in persons:
            result.append(f"[{p.id}] {p.name} ({p.relation}) - {len(p.emails)} emails, {len(p.phones)} phones")
        return "\n".join(result)

    @mcp.tool()
    def footprint_get_person(person_id: int = None, name: str = None) -> str:
        """Get full details for a protected person.

        Args:
            person_id: Person ID (preferred)
            name: Person name (fuzzy match)
        """
        if person_id:
            person = db.get_person(person_id)
        elif name:
            persons = db.list_persons()
            person = next((p for p in persons if name.lower() in p.name.lower()), None)
        else:
            return "Provide either person_id or name."
        if not person:
            return "Person not found."
        return json.dumps(person.to_dict(), indent=2)

    @mcp.tool()
    def footprint_update_person(
        person_id: int,
        name: str = None,
        emails: list[str] = None,
        phones: list[str] = None,
        addresses: list[str] = None,
        usernames: list[str] = None,
        date_of_birth: str = None,
        relation: str = None,
    ) -> str:
        """Update a protected person's information.

        Args:
            person_id: ID of the person to update
            name: New name (optional)
            emails: New email list (optional)
            phones: New phone list (optional)
            addresses: New address list (optional)
            usernames: New username list (optional)
            date_of_birth: New DOB (optional)
            relation: New relation (optional)
        """
        kwargs = {}
        for field, value in [
            ("name", name), ("emails", emails), ("phones", phones),
            ("addresses", addresses), ("usernames", usernames),
            ("date_of_birth", date_of_birth), ("relation", relation),
        ]:
            if value is not None:
                kwargs[field] = value
        if not kwargs:
            return "No fields to update."
        db.update_person(person_id, **kwargs)
        person = db.get_person(person_id)
        return json.dumps(person.to_dict(), indent=2)
