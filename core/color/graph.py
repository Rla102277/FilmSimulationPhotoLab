"""Camera-independent, non-destructive color graph definition.

The graph is deliberately a small JSON document.  It is the master editing
representation; compiled LUTs are derived artifacts and are never used as the
source of truth.
"""

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

MANUAL_NODE_TYPES = {
    "manual",
    "exposure", "contrast", "highlights", "shadows", "whites", "blacks",
    "temperature", "tint", "saturation", "vibrance",
    "shadow_grade", "midtone_grade", "highlight_grade",
    "film_toe", "film_shoulder", "black_lift", "highlight_rolloff",
}

SOURCE_NODE_TYPES = {"cube_lut", "lut", "matrix", "curve", "tone_curve",
                     "huesat_table", "look_table", "table", "settings", "source_component"}
ALL_NODE_TYPES = set(NODE_ORDER) | MANUAL_NODE_TYPES | SOURCE_NODE_TYPES


def default_color_graph() -> dict:
    return {
        "version": 1,
        "nodes": [
            {"id": node, "type": node, "enabled": node not in {"matrix", "monochrome_filter", "grain"},
             "strength": 1.0}
            for node in NODE_ORDER
        ],
        "principle": "Targets may omit unsupported nodes; compilers translate intent into target capabilities.",
    }


def validate_color_graph(graph: dict) -> dict:
    if not isinstance(graph, dict):
        raise ValueError("Color graph must be an object")
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("Color graph nodes must be a list")
    if len(nodes) > 512:
        raise ValueError("Color graph cannot contain more than 512 nodes")
    seen: set[str] = set()
    for position, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise ValueError("Color graph nodes must be objects")
        node_type = node.get("type")
        if node_type not in ALL_NODE_TYPES:
            raise ValueError(f"Unknown color graph node: {node_type}")
        node_id = str(node.get("id") or f"{node_type}:{position}")
        if node_id in seen:
            raise ValueError(f"Duplicate color graph node id: {node_id}")
        seen.add(node_id)
        strength = node.get("strength", 1.0)
        if not isinstance(strength, (int, float)) or not 0 <= float(strength) <= 2:
            raise ValueError(f"Node strength must be between 0 and 2: {node_id}")
        if "enabled" in node and not isinstance(node["enabled"], bool):
            raise ValueError(f"Node enabled must be boolean: {node_id}")
        if "solo" in node and not isinstance(node["solo"], bool):
            raise ValueError(f"Node solo must be boolean: {node_id}")
    identifiers = {str(node.get("id") or node.get("type")) for node in nodes}
    types = {str(node.get("type")) for node in nodes}
    if not {"input", "output"}.issubset(identifiers | types):
        raise ValueError("Color graph must contain input and output nodes")
    return graph


def active_nodes(graph: dict) -> list[dict]:
    """One activation rule shared by validation, source hydration and evaluation."""
    nodes = [n for n in graph["nodes"] if n.get("enabled", True) and n.get("strength", 1) != 0]
    solo = any(n.get("solo") for n in nodes)
    return [n for n in nodes if not solo or n.get("solo") or n.get("type") in {"input", "output", "camera_normalization"}]


def graph_status(graph: dict) -> dict:
    """Return a non-throwing validation/capability report for an editor."""
    try:
        validate_color_graph(graph)
    except (TypeError, ValueError) as exc:
        return {"valid": False, "ready": False, "errors": [str(exc)], "nodes": []}
    nodes = graph["nodes"]
    unsupported = []
    errors = []
    for node in active_nodes(graph):
        component = node.get("component") if isinstance(node.get("component"), dict) else {}
        kind = node.get("component_type") or component.get("type") or node.get("type")
        if kind == "manual":
            params = node.get("params") if isinstance(node.get("params"), dict) else {}
            kind = params.get("kind") or params.get("control") or kind
        if node.get("unsupported_reason"):
            errors.append({"id": node.get("id"), "error": node["unsupported_reason"]})
        if kind in {"huesat_table", "look_table", "table", "settings", "grain"}:
            unsupported.append({
                "id": node.get("id", node.get("type")),
                "type": kind,
                "blendable": False,
                "reason": "No safe camera-independent interpolation is defined",
            })
        if node.get("unresolved_source"):
            errors.append({
                "id": node.get("id", node.get("type")),
                "error": f"Source component is unresolved: {node['unresolved_source']}",
            })
        if node.get("source_id") != None or node.get("component_id") != None:
            if not node.get("source_id") or not node.get("component_id"):
                errors.append({
                    "id": node.get("id", node.get("type")),
                    "error": "source_id and component_id are both required for a source component",
                })
        if kind in {"lut", "cube_lut"} and not (node.get("cube") or node.get("cube_data") or
                                                 node.get("data") or node.get("source_id")):
            errors.append({"id": node.get("id", node.get("type")),
                           "error": "LUT node has no CUBE data or source component reference"})
        if kind in {"matrix", "forward_matrix", "color_matrix"} and not (
                node.get("matrix") or node.get("values") or node.get("source_id")):
            errors.append({"id": node.get("id", node.get("type")),
                           "error": "Matrix node has no matrix data or source component reference"})
        if kind in {"curve", "tone_curve", "profile_tone_curve"} and not (
                node.get("points") or node.get("curve") or node.get("source_id")):
            errors.append({"id": node.get("id", node.get("type")),
                           "error": "Curve node has no points or source component reference"})
    return {
        "valid": not errors,
        "ready": not unsupported and not errors,
        "errors": errors,
        "unsupported": unsupported,
        "nodes": [{"id": n.get("id", n.get("type")), "type": n.get("type"),
                   "enabled": n.get("enabled", True),
                   "strength": float(n.get("strength", 1.0))}
                  for n in nodes],
        "master_representation": "editable_graph",
        "export": "17^3 CUBE",
    }
