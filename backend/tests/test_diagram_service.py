import pytest
from backend.services.diagram_service import DiagramService, NodeType

def test_builds_nodes_from_recommendation():
    svc = DiagramService()
    raw = {
        "recommendation": "Singapore Discretionary Trust",
        "entities": [
            {"label": "the Client", "type": "individual", "role": "Settlor", "jurisdiction": "India"},
            {"label": "Singapore Discretionary Trust", "type": "trust", "role": "Trust", "jurisdiction": "Singapore"},
            {"label": "VCC", "type": "company", "role": "Investment Vehicle", "jurisdiction": "Singapore"},
        ],
        "edges": [
            {"source": 0, "target": 1, "label": "Settlor"},
            {"source": 1, "target": 2, "label": "Ownership"},
        ]
    }
    result = svc.build_diagram_data(raw)
    assert len(result["nodes"]) == 3
    assert result["nodes"][0]["type"] == "individual"
    assert result["nodes"][1]["type"] == "trust"
    assert len(result["edges"]) == 2
    assert result["edges"][0]["label"] == "Settlor"
    assert result["edges"][1]["label"] == "Ownership"  # second edge label check


def test_out_of_bounds_edges_skipped():
    svc = DiagramService()
    raw = {
        "entities": [{"label": "A", "type": "individual"}],
        "edges": [
            {"source": 0, "target": 99, "label": "Invalid"},
            {"source": 0, "target": 0, "label": "Valid"},
        ]
    }
    result = svc.build_diagram_data(raw)
    # Out-of-bounds edge should be skipped
    assert len(result["edges"]) == 1
    assert result["edges"][0]["label"] == "Valid"
