"""Tests for pure helpers in ingestion (freshservice) and retrieval (search_tickets)."""

import math

import search_tickets
from freshservice import sanitize_metadata, _coerce_value
from search_tickets import summarize, _triples


def test_coerce_value_handles_none_floats_and_primitives():
    assert _coerce_value(None) == ""
    assert _coerce_value(True) is True
    assert _coerce_value(5) == 5
    assert _coerce_value("x") == "x"
    assert _coerce_value(math.nan) == 0.0
    assert _coerce_value(math.inf) == 0.0


def test_sanitize_metadata_coerces_to_chroma_primitives():
    out = sanitize_metadata({"a": None, "b": 5, "c": 1.5, "d": [1, 2], "e": True})
    assert out["a"] == ""
    assert out["b"] == 5
    assert out["c"] == 1.5
    assert out["e"] is True
    assert isinstance(out["d"], str)  # non-primitives coerced to str
    assert all(isinstance(v, (bool, int, float, str)) for v in out.values())


def test_summarize_ranks_top_agents_and_category_paths():
    results = [
        ("d1", {"responder_name": "Alice", "group_name": "Apps",
                "category": "Software", "subcategory": "Revit", "item": "Crash"}, 0.1),
        ("d2", {"responder_name": "Alice", "group_name": "Apps",
                "category": "Software", "subcategory": "Revit", "item": "Crash"}, 0.2),
        ("d3", {"responder_name": "Bob", "group_name": "Net",
                "category": "Network", "subcategory": "VPN", "item": None}, 0.3),
    ]
    s = summarize(results)
    assert s["total"] == 3
    assert s["top_agents"][0]["name"] == "Alice"
    assert s["top_agents"][0]["pct"] == round(2 / 3 * 100, 1)
    assert s["top_paths"][0]["path"] == "Software → Revit → Crash"


def test_triples_skips_none_distances():
    res = {
        "documents": [["d1", "d2"]],
        "metadatas": [[{"ticket_id": 1}, {"ticket_id": 2}]],
        "distances": [[0.1, None]],  # the None-distance row must be dropped
    }
    out = _triples(res)
    assert len(out) == 1
    assert out[0][0] == "d1"
    assert out[0][2] == 0.1


def test_resolve_assigned_agent_keeps_known_name_without_network(monkeypatch):
    # A known name short-circuits and must NOT trigger an agent lookup.
    calls = {"n": 0}

    def _boom(_rid):
        calls["n"] += 1
        return "should-not-be-called"

    monkeypatch.setattr(search_tickets, "get_agent_name", _boom)
    out = search_tickets._resolve_assigned_agent({"responder_name": "Alice", "responder_id": 5})
    assert out["responder_name"] == "Alice"
    assert calls["n"] == 0


def test_resolve_assigned_agent_resolves_from_metadata_responder_id(monkeypatch):
    monkeypatch.setattr(search_tickets, "get_agent_name", lambda rid: "Resolved Name")
    out = search_tickets._resolve_assigned_agent({"responder_name": "Unknown", "responder_id": 7})
    assert out["responder_name"] == "Resolved Name"
