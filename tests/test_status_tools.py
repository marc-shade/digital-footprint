"""Test status dashboard tool."""

from digital_footprint.tools.status_tools import register_status_tools


class FakeMCP:
    def __init__(self):
        self.tools = {}
    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def test_status_empty(tmp_db):
    mcp = FakeMCP()
    register_status_tools(mcp, tmp_db)
    result = mcp.tools["footprint_status"]()
    assert "Protected persons: 0" in result
    assert "Last scan:          never" in result


def test_status_with_data(tmp_db):
    tmp_db.insert_person(name="Marc", emails=["marc@example.com"])
    from digital_footprint.models import Broker
    tmp_db.insert_broker(Broker(slug="spokeo", name="Spokeo", url="https://spokeo.com", category="people_search"))
    mcp = FakeMCP()
    register_status_tools(mcp, tmp_db)
    result = mcp.tools["footprint_status"]()
    assert "Protected persons: 1" in result
    assert "Broker registry:   1" in result
