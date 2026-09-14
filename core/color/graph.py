"""Camera-independent color graph definition."""

from __future__ import annotations


NODE_ORDER = (
    "input",
    "camera_normalization",
    "white_balance_intent",
    "tone",
    "matrix",
    "lut",
    "shadow_shaping",
    "highlight_shaping",
    "chroma",
    "monochrome_filter",
    "grain",
    "output",
)


def default_color_graph() -> dict:
    return {
        "version": 1,
        "nodes": [{"type": node, "enabled": node not in {"matrix", "monochrome_filter", "grain"}} for node in NODE_ORDER],
        "principle": "Targets may omit unsupported nodes; compilers translate intent into target capabilities.",
    }


def validate_color_graph(graph: dict) -> dict:
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("Color graph nodes must be a list")
    seen: set[str] = set()
    previous = -1
    for node in nodes:
        node_type = node.get("type") if isinstance(node, dict) else None
        if node_type not in NODE_ORDER:
            raise ValueError(f"Unknown color graph node: {node_type}")
        index = NODE_ORDER.index(node_type)
        if index <= previous or node_type in seen:
            raise ValueError("Color graph nodes must be unique and in processing order")
        seen.add(node_type)
        previous = index
    if not {"input", "output"}.issubset(seen):
        raise ValueError("Color graph must contain input and output nodes")
    return graph
