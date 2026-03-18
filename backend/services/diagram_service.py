from enum import Enum

class NodeType(str, Enum):
    TRUST = "trust"
    COMPANY = "company"
    INDIVIDUAL = "individual"

# Layout constants
NODE_WIDTH = 180
NODE_HEIGHT = 80
HORIZONTAL_GAP = 220
VERTICAL_GAP = 140


def _node_style(node_type: str) -> dict:
    base = {"fontSize": 12, "fontWeight": 500}
    if node_type == NodeType.TRUST:
        return {**base, "background": "transparent", "border": "none"}
    if node_type == NodeType.COMPANY:
        return {
            **base,
            "background": "#f8fafc",
            "border": "1.5px solid #334155",
            "borderRadius": "6px",
            "padding": "10px 16px",
            "minWidth": f"{NODE_WIDTH}px",
        }
    # individual and unknown
    return {**base, "background": "transparent", "border": "none"}


class DiagramService:
    def build_diagram_data(self, raw: dict) -> dict:
        """Convert LLM recommendation entity list into React Flow node/edge JSON."""
        entities = raw.get("entities", [])
        raw_edges = raw.get("edges", [])

        nodes = []
        for i, entity in enumerate(entities):
            col = i % 3
            row = i // 3
            nodes.append({
                "id": f"node_{i}",
                "type": entity.get("type", "company"),
                "position": {"x": col * HORIZONTAL_GAP + 50, "y": row * VERTICAL_GAP + 50},
                "data": {
                    "label": entity.get("label", ""),
                    "jurisdiction": entity.get("jurisdiction", ""),
                    "role": entity.get("role", ""),
                    "tax_treatment": entity.get("tax_treatment", ""),
                    "rationale": entity.get("rationale", ""),
                    "source": entity.get("source", ""),
                },
                "style": _node_style(entity.get("type", "company")),
            })

        edges = [
            {
                "id": f"edge_{i}",
                "source": f"node_{e['source']}",
                "target": f"node_{e['target']}",
                "label": e.get("label", ""),
                "animated": False,
                "style": {"stroke": "#64748b", "strokeWidth": 1.5},
                "labelStyle": {"fontSize": 11, "fill": "#475569"},
            }
            for i, e in enumerate(raw_edges)
        ]

        return {"nodes": nodes, "edges": edges}
