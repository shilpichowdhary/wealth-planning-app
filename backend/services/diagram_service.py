import logging
from enum import Enum

logger = logging.getLogger(__name__)

class NodeType(str, Enum):
    TRUST = "trust"
    COMPANY = "company"
    INDIVIDUAL = "individual"

# Layout constants
NODE_WIDTH = 180
NODE_HEIGHT = 80
HORIZONTAL_GAP = 220
VERTICAL_GAP = 140


class DiagramService:
    @staticmethod
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
                "style": DiagramService._node_style(entity.get("type", "company")),
            })

        edges = []
        for i, e in enumerate(raw_edges):
            src_idx = e.get('source')
            tgt_idx = e.get('target')
            if src_idx is None or tgt_idx is None:
                logger.warning("Edge %d missing source or target, skipping", i)
                continue
            if not (0 <= src_idx < len(entities) and 0 <= tgt_idx < len(entities)):
                logger.warning(
                    "Edge %d has out-of-bounds indices (src=%s, tgt=%s, entity_count=%d), skipping",
                    i, src_idx, tgt_idx, len(entities)
                )
                continue
            edges.append({
                "id": f"edge_{i}",
                "source": f"node_{src_idx}",
                "target": f"node_{tgt_idx}",
                "label": e.get("label", ""),
                "animated": False,
                "style": {"stroke": "#64748b", "strokeWidth": 1.5},
                "labelStyle": {"fontSize": 11, "fill": "#475569"},
            })

        return {"nodes": nodes, "edges": edges}
