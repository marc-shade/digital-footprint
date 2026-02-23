"""Test person management tools end-to-end."""

import json
from digital_footprint.tools.person_tools import register_person_tools


class FakeMCP:
    """Minimal MCP mock that captures registered tools."""
    def __init__(self):
        self.tools = {}
    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def test_add_and_get_person(tmp_db):
    mcp = FakeMCP()
    register_person_tools(mcp, tmp_db)

    result = mcp.tools["footprint_add_person"](
        name="Marc Shade",
        emails=["marc@example.com"],
        phones=["555-0100"],
    )
    data = json.loads(result)
    assert data["name"] == "Marc Shade"
    assert data["emails"] == ["marc@example.com"]
    assert "id" in data

    result2 = mcp.tools["footprint_get_person"](person_id=data["id"])
    data2 = json.loads(result2)
    assert data2["name"] == "Marc Shade"


def test_list_persons(tmp_db):
    mcp = FakeMCP()
    register_person_tools(mcp, tmp_db)
    mcp.tools["footprint_add_person"](name="Alice", emails=["a@b.com"])
    mcp.tools["footprint_add_person"](name="Bob", emails=["b@b.com"])
    result = mcp.tools["footprint_list_persons"]()
    assert "Alice" in result
    assert "Bob" in result


def test_update_person(tmp_db):
    mcp = FakeMCP()
    register_person_tools(mcp, tmp_db)
    mcp.tools["footprint_add_person"](name="Marc Shade", emails=["marc@example.com"])
    result = mcp.tools["footprint_update_person"](person_id=1, phones=["555-9999"])
    data = json.loads(result)
    assert data["phones"] == ["555-9999"]


def test_get_person_by_name(tmp_db):
    mcp = FakeMCP()
    register_person_tools(mcp, tmp_db)
    mcp.tools["footprint_add_person"](name="Marc Shade", emails=["marc@example.com"])
    result = mcp.tools["footprint_get_person"](name="marc")
    data = json.loads(result)
    assert data["name"] == "Marc Shade"
