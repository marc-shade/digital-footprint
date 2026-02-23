"""Test broker registry tools end-to-end."""

import json
from digital_footprint.models import Broker
from digital_footprint.tools.broker_tools import register_broker_tools


class FakeMCP:
    def __init__(self):
        self.tools = {}
    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def _seed_brokers(db):
    db.insert_broker(Broker(slug="spokeo", name="Spokeo", url="https://spokeo.com", category="people_search", difficulty="easy", automatable=True, opt_out_method="web_form"))
    db.insert_broker(Broker(slug="acxiom", name="Acxiom", url="https://acxiom.com", category="marketing", difficulty="hard", opt_out_method="email"))
    db.insert_broker(Broker(slug="beenverified", name="BeenVerified", url="https://beenverified.com", category="people_search", difficulty="easy", automatable=True, opt_out_method="web_form"))


def test_list_brokers(tmp_db):
    _seed_brokers(tmp_db)
    mcp = FakeMCP()
    register_broker_tools(mcp, tmp_db)
    result = mcp.tools["footprint_list_brokers"]()
    assert "3 brokers" in result
    assert "spokeo" in result


def test_list_brokers_filtered(tmp_db):
    _seed_brokers(tmp_db)
    mcp = FakeMCP()
    register_broker_tools(mcp, tmp_db)
    result = mcp.tools["footprint_list_brokers"](category="marketing")
    assert "1 brokers" in result
    assert "acxiom" in result


def test_get_broker(tmp_db):
    _seed_brokers(tmp_db)
    mcp = FakeMCP()
    register_broker_tools(mcp, tmp_db)
    result = mcp.tools["footprint_get_broker"](slug="spokeo")
    data = json.loads(result)
    assert data["name"] == "Spokeo"
    assert data["opt_out_method"] == "web_form"


def test_broker_stats(tmp_db):
    _seed_brokers(tmp_db)
    mcp = FakeMCP()
    register_broker_tools(mcp, tmp_db)
    result = mcp.tools["footprint_broker_stats"]()
    assert "Total brokers: 3" in result
    assert "people_search: 2" in result
    assert "Automatable: 2" in result
