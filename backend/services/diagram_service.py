import logging
from enum import Enum

logger = logging.getLogger(__name__)

class NodeType(str, Enum):
    TRUST = "trust"
    COMPANY = "company"
    INDIVIDUAL = "individual"

# Initial position grid — only used as a fallback. The frontend re-runs dagre
# layout on every load, so these coordinates are overwritten.
HORIZONTAL_GAP = 220
VERTICAL_GAP = 140


class DiagramService:
    """Convert LLM-emitted entities/edges into React Flow node/edge JSON.

    Visual styling lives entirely in the frontend custom node components
    (TrustNode, CompanyNode, IndividualNode) and the StructureDiagram's
    defaultEdgeOptions. This service emits structural data only — assigning
    inline `style` props here would produce a doubled outline (React Flow's
    node wrapper + the inner component's wrapper).
    """

    def build_diagram_data(self, raw: dict) -> dict:
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
            })

        return {"nodes": nodes, "edges": edges}
