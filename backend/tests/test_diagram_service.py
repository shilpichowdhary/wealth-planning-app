import pytest
from backend.services.diagram_service import DiagramService, NodeType
from backend.services.llm_service import extract_diagram_json

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


def test_extract_diagram_json_returns_none_for_malformed_entity():
    """An entity missing its required `type` field is invalid; the validator
    must reject the whole diagram rather than letting the bad entity reach React Flow."""
    text = '''Here is the diagram:
```json
{"entities": [{"label": "Trust"}], "edges": []}
```
'''
    assert extract_diagram_json(text) is None


def test_extract_diagram_json_returns_none_for_invalid_entity_type():
    """The `type` field is constrained to individual/trust/company."""
    text = '''```json
{"entities": [{"type": "spaceship", "label": "X"}], "edges": []}
```'''
    assert extract_diagram_json(text) is None


def test_extract_diagram_json_returns_dict_for_well_formed_input():
    text = '''```json
{"entities": [{"type": "trust", "label": "T", "jurisdiction": "Jersey"}], "edges": []}
```'''
    result = extract_diagram_json(text)
    assert result is not None
    assert len(result["entities"]) == 1
    assert result["entities"][0]["type"] == "trust"


def test_extract_diagram_json_returns_none_for_negative_edge_index():
    """The Pydantic schema constrains source/target to non-negative."""
    text = '''```json
{"entities": [{"type": "trust", "label": "T"}], "edges": [{"source": -1, "target": 0, "label": "owns 100%"}]}
```'''
    assert extract_diagram_json(text) is None
