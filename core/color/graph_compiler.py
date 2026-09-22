"""Deterministic graph evaluation and 17-cube compilation.

This module intentionally uses only NumPy and the existing CUBE parser.  Every
node is evaluated in graph order, so reordering remains meaningful and the
editable graph stays authoritative until export.
"""

from __future__ import annotations

import colorsys
from typing import Any

import numpy as np

from core.color.cube import CubeLUT, parse_cube, resample_cube, sample_cube
from core.color.graph import MANUAL_NODE_TYPES, SOURCE_NODE_TYPES, graph_status, validate_color_graph, active_nodes


def _strength(node: dict) -> float:
    return float(node.get("strength", node.get("amount", 1.0)))


def _blend(original: np.ndarray, transformed: np.ndarray, strength: float) -> np.ndarray:
    return original + (transformed - original) * strength


def _cube_from_node(node: dict) -> CubeLUT:
    cached = node.get("_parsed_cube")
    if isinstance(cached, CubeLUT):
        return cached
    value = node.get("cube") or node.get("cube_data") or node.get("data")
    if isinstance(value, dict):
        value = value.get("cube") or value.get("text")
    if isinstance(value, str):
        return parse_cube(value.encode("utf-8"))
    if isinstance(value, bytes):
        return parse_cube(value)
    raise ValueError(f"Node {node.get('id', node.get('type'))} has no CUBE data")


_sample_cube = sample_cube


def _curve_value(x: np.ndarray, points: Any) -> np.ndarray:
    if isinstance(points, dict):
        points = points.get("points") or points.get("values") or points.get("curve")
    if not isinstance(points, (list, tuple)) or len(points) < 2:
        raise ValueError("Curve node requires at least two [input, output] points")
    parsed = np.asarray(points, dtype=np.float32)
    if parsed.ndim != 2 or parsed.shape[1] != 2:
        raise ValueError("Curve points must be [input, output] pairs")
    if not np.isfinite(parsed).all() or len(np.unique(parsed[:, 0])) != len(parsed):
        raise ValueError("Curve points must be finite with distinct inputs")
    order = np.argsort(parsed[:, 0])
    return np.interp(x, parsed[order, 0], parsed[order, 1])


def _matrix(node: dict) -> np.ndarray:
    values = node.get("matrix") or node.get("values") or node.get("data")
    if isinstance(values, dict):
        values = values.get("matrix")
    matrix = np.asarray(values, dtype=np.float32)
    if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
        raise ValueError("Matrix node requires a 3x3 matrix")
    return matrix


def _hsv_grade(rgb: np.ndarray, params: dict, mask: np.ndarray) -> np.ndarray:
    """Tint toward the selected hue, with continuous tonal weighting."""
    amount = float(params.get("amount", params.get("saturation", 0.0)))
    hue = float(params.get("hue", 0.0)) / 360.0
    luminance = float(params.get("luminance", 0.0))
    luma = np.sum(rgb * [0.2126, 0.7152, 0.0722], axis=-1, keepdims=True)
    tint = np.asarray(colorsys.hsv_to_rgb(hue % 1, 1, 1), dtype=np.float32)
    tint -= np.sum(tint * [0.2126, 0.7152, 0.0722])
    if amount >= 0:
        transformed = rgb + tint * amount * 0.5
    else:
        transformed = luma + (rgb - luma) * (1 + amount)
    transformed += luminance * 0.25
    return _blend(rgb, transformed, mask[..., None])


def _manual_transform(rgb: np.ndarray, node_type: str, params: dict) -> np.ndarray:
    out = rgb.copy()
    if node_type == "exposure":
        out *= 2.0 ** float(params.get("value", params.get("exposure", 0.0)))
    elif node_type == "contrast":
        factor = float(params.get("value", params.get("contrast", 0.0)))
        factor = 1.0 + factor if -1 <= factor <= 1 else factor
        out = (out - 0.5) * factor + 0.5
    elif node_type in {"highlights", "shadows", "whites", "blacks"}:
        value = float(params.get("value", params.get(node_type, 0.0)))
        if node_type == "highlights":
            out += np.maximum(out - 0.5, 0) * value
        elif node_type == "shadows":
            out += np.maximum(0.5 - out, 0) * value
        elif node_type == "whites":
            out += np.maximum(out - 0.75, 0) * value
        else:
            out += np.maximum(0.25 - out, 0) * value
    elif node_type == "temperature":
        value = float(params.get("value", params.get("temperature", 0.0)))
        out *= np.asarray([1.0 + value, 1.0, 1.0 - value], dtype=np.float32)
    elif node_type == "tint":
        value = float(params.get("value", params.get("tint", 0.0)))
        out *= np.asarray([1.0 + value * 0.35, 1.0 - value * 0.2, 1.0 + value * 0.35], dtype=np.float32)
    elif node_type in {"saturation", "vibrance"}:
        value = float(params.get("value", params.get(node_type, 0.0)))
        luma = np.sum(out * np.asarray([0.2126, 0.7152, 0.0722], dtype=np.float32), axis=-1, keepdims=True)
        factor = 1.0 + value * (1.0 - np.abs(out - luma)) if node_type == "vibrance" else 1.0 + value
        out = luma + (out - luma) * factor
    elif node_type in {"shadow_grade", "midtone_grade", "highlight_grade"}:
        luma = np.sum(out * np.asarray([0.2126, 0.7152, 0.0722]), axis=-1)
        position = np.clip(luma - float(params.get("balance", 0)) * 0.25, 0, 1)
        if node_type == "shadow_grade":
            mask = (1 - position) ** 2
        elif node_type == "highlight_grade":
            mask = position ** 2
        else:
            mask = 4 * position * (1 - position)
        out = _hsv_grade(out, params, mask)
    elif node_type in {"film_toe", "black_lift"}:
        value = float(params.get("value", params.get("amount", 0.0)))
        out = out + np.maximum(0.2 - out, 0) * value
    elif node_type in {"film_shoulder", "highlight_rolloff"}:
        value = float(params.get("value", params.get("amount", 0.0)))
        out = out - np.maximum(out - 0.75, 0) * value
    return out


def _node_transform(rgb: np.ndarray, node: dict) -> tuple[np.ndarray, bool, str | None]:
    node_type = str(node.get("component_type") or node.get("type"))
    strength = _strength(node)
    if node_type == "manual":
        node_type = str((node.get("params") or {}).get("kind") or
                        (node.get("params") or {}).get("control") or "unsupported")
    if node_type in {"input", "output", "camera_normalization", "white_balance_intent", "tone",
                     "shadow_shaping", "highlight_shaping", "chroma"}:
        return rgb, True, None
    if node_type == "monochrome_filter":
        params = node.get("params") or {}
        weights = np.asarray([0.2126, 0.7152, 0.0722])
        targets = {"yellowFilter": [0.4, 0.55, 0.05], "orangeFilter": [0.6, 0.35, 0.05],
                   "redFilter": [0.8, 0.15, 0.05], "greenFilter": [0.1, 0.85, 0.05]}
        for key, target in targets.items():
            weights += float(params.get(key, 0)) * (np.asarray(target) - [0.2126, 0.7152, 0.0722])
        weights = np.maximum(weights, 0)
        weights /= weights.sum()
        gray = np.repeat(np.sum(rgb * weights, axis=-1, keepdims=True), 3, axis=-1)
        return _blend(rgb, gray, strength), True, None
    if node_type in {"huesat_table", "look_table", "table", "settings", "grain"}:
        return rgb, False, "No safe interpolation strategy for this component"
    if node_type in {"cube_lut", "lut"}:
        transformed = _sample_cube(rgb, _cube_from_node(node))
        return _blend(rgb, transformed, strength), True, None
    if node_type in {"matrix", "forward_matrix", "color_matrix", "camera_calibration"}:
        matrix = _matrix(node)
        effective = np.eye(3, dtype=np.float32) + strength * (matrix - np.eye(3, dtype=np.float32))
        return np.einsum("...c,dc->...d", rgb, effective), True, None
    if node_type in {"curve", "tone_curve", "profile_tone_curve"}:
        points = node.get("points") or node.get("curve") or node.get("data")
        transformed = np.stack([_curve_value(rgb[..., channel], points) for channel in range(3)], axis=-1)
        channel = node.get("channel")
        if channel is not None:
            if channel not in (0, 1, 2):
                raise ValueError("Curve channel must be 0, 1 or 2")
            transformed[..., [i for i in range(3) if i != channel]] = rgb[..., [i for i in range(3) if i != channel]]
        return _blend(rgb, transformed, strength), True, None
    if node_type in MANUAL_NODE_TYPES:
        transformed = _manual_transform(rgb, node_type, node.get("params") or node.get("data") or node)
        return _blend(rgb, transformed, strength), True, None
    if node_type == "source_component":
        component = node.get("component") or node.get("data") or {}
        nested = dict(component) if isinstance(component, dict) else {}
        nested.setdefault("type", nested.get("component_type", "unsupported"))
        nested["strength"] = strength
        return _node_transform(rgb, nested)
    return rgb, False, f"Unsupported graph node type: {node_type}"


def evaluate_graph(graph: dict, size: int = 17, *, clip_output: bool = True) -> tuple[CubeLUT, dict]:
    validate_color_graph(graph)
    if not 2 <= size <= 65:
        raise ValueError("Compiled graph cube size must be between 2 and 65")
    nodes = []
    for source_node in active_nodes(graph):
        node = dict(source_node)
        if str(node.get("component_type") or node.get("type")) in {"cube_lut", "lut"}:
            node["_parsed_cube"] = _cube_from_node(node)
        nodes.append(node)
    solos = [node for node in nodes if node.get("solo") and node.get("enabled", True)]
    unsupported: list[dict] = []
    axis = np.linspace(0.0, 1.0, size, dtype=np.float32)
    values = np.asarray([
        (red, green, blue)
        for blue in axis for green in axis for red in axis
    ], dtype=np.float32)
    for node in nodes:
        node_id = node.get("id", node.get("type"))
        node_type = node.get("type")
        if node_type in {"input", "output"}:
            continue
        if not node.get("enabled", True) or (solos and not node.get("solo")):
            continue
        values, blendable, reason = _node_transform(values, node)
        if not np.isfinite(values).all():
            raise ValueError(f"Node {node_id} produced non-finite color values")
        if not blendable:
            unsupported.append({"id": node_id, "type": node_type, "blendable": False, "reason": reason})
    if graph.get("base") == 1:
        values = np.repeat(np.sum(values * [0.2126, 0.7152, 0.0722], axis=-1, keepdims=True), 3, axis=-1)
    range_report = {
        "below_zero_by_channel": np.sum(values < 0, axis=0).tolist(),
        "above_one_by_channel": np.sum(values > 1, axis=0).tolist(),
        "exact_zero_by_channel": np.sum(values == 0, axis=0).tolist(),
        "min": float(values.min()), "max": float(values.max()),
        "clamped_at_output": clip_output,
    }
    if clip_output:
        values = np.clip(values, 0.0, 1.0)
    unique_unsupported = {item["id"]: item for item in unsupported}
    cube = CubeLUT(str(graph.get("name", "Compiled graph")), size, (0.0, 0.0, 0.0),
                   (1.0, 1.0, 1.0), values.astype(np.float32, copy=False))
    report = graph_status(graph)
    report.update({"compiled": True, "range": range_report, "grid_size": size,
                   "export": f"{size}^3 CUBE", "unsupported": list(unique_unsupported.values()),
                   "ready": report.get("ready", True) and not unique_unsupported})
    return cube, report


def compile_graph_cube(graph: dict, size: int = 17, *, clip_output: bool = True) -> tuple[bytes, dict]:
    cube, report = evaluate_graph(graph, size=size, clip_output=clip_output)
    title = str(graph.get("name", "Compiled graph"))
    if any(ord(c) < 32 or ord(c) > 126 or c == '"' for c in title):
        raise ValueError("CUBE title must contain printable ASCII without quotes")
    lines = [
        f'TITLE "{title}"',
        f"LUT_3D_SIZE {cube.size}",
        "DOMAIN_MIN 0.0 0.0 0.0",
        "DOMAIN_MAX 1.0 1.0 1.0",
    ]
    lines.extend(" ".join(f"{float(value):.9f}" for value in row) for row in cube.values)
    return (("\n".join(lines) + "\n").encode("ascii"), report)
