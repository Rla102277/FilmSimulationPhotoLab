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
from core.color.source_transforms import dcp_transform, preset_transform, selective, compress
from core.color.graph import MANUAL_NODE_TYPES, SOURCE_NODE_TYPES, graph_status, validate_color_graph


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
    order = np.argsort(parsed[:, 0])
    return np.interp(x, parsed[order, 0], parsed[order, 1])


def _matrix(node: dict) -> np.ndarray:
    values = node.get("matrix") or node.get("values") or node.get("data")
    if isinstance(values, dict):
        values = values.get("matrix")
    matrix = np.asarray(values, dtype=np.float32)
    if matrix.shape != (3, 3):
        raise ValueError("Matrix node requires a 3x3 matrix")
    return matrix


def _hsv_grade(rgb: np.ndarray, params: dict, mask: np.ndarray) -> np.ndarray:
    amount = float(params.get("amount", params.get("saturation", 0.0)))
    hue = float(params.get("hue", 0.0)) / 360.0
    color = np.array(colorsys.hsv_to_rgb(hue % 1, 1, 1))
    color -= np.sum(color * np.array([.2126, .7152, .0722]))
    y = np.sum(rgb * np.array([.2126, .7152, .0722]), axis=-1)
    envelope = np.sin(np.pi * np.clip(y, 0, 1))
    return compress(rgb + mask[..., None] * envelope[..., None] *
                    (color * amount * .35 + float(params.get("luminance", 0)) * .25))


def _manual_transform(rgb: np.ndarray, node_type: str, params: dict) -> np.ndarray:
    out = rgb.copy()
    if node_type == "exposure":
        out *= 2.0 ** float(params.get("value", params.get("exposure", 0.0)))
    elif node_type == "contrast":
        factor = float(params.get("value", params.get("contrast", 0.0)))
        factor = 1.0 + factor
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
        luma = np.clip(luma - float(params.get("balance",0))*.2, 0, 1)
        if node_type == "shadow_grade":
            mask = np.exp(-.5*((luma-.22)/.23)**2)
        elif node_type == "highlight_grade":
            mask = np.exp(-.5*((luma-.78)/.23)**2)
        else:
            mask = np.exp(-.5*((luma-.5)/.22)**2)
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
        if node.get("params") or node.get("data"):
            raise ValueError(f"{node_type} parameters have no implemented transform; use an explicit supported node")
        return rgb, True, None
    if node_type in {"huesat_table", "look_table", "table", "settings", "grain"}:
        return rgb, False, "No safe interpolation strategy for this component"
    if node_type == "dcp_creative":
        return _blend(rgb, dcp_transform(rgb, node), strength), True, "DCP bounded display interpretation"
    if node_type == "preset_creative":
        return _blend(rgb, preset_transform(rgb, node["settings"], node.get("include_curves", False)), strength), True, "Selected preset HSL interpretation"
    if node_type == "selective_color":
        return _blend(rgb, selective(rgb, node.get("params", {})), strength), True, None
    if node_type == "monochrome_filter":
        params = node.get("params", {}); value = float(params.get("value", 1))
        weights = np.array({"yellowFilter": [.32,.60,.08], "orangeFilter": [.45,.50,.05],
                            "redFilter": [.65,.30,.05], "greenFilter": [.15,.75,.10]}.get(params.get("filter"), [.2126,.7152,.0722]))
        gray = np.sum(rgb * weights, axis=-1, keepdims=True)
        return _blend(rgb, np.repeat(gray,3,axis=-1), strength*value), True, None
    if node_type == "blend":
        branches = node.get("branches", [])
        weights = [float(branch.get("weight", 1)) for branch in branches]
        if not weights or not np.isfinite(weights).all() or min(weights)<0 or sum(weights)<=0:
            raise ValueError("Blend needs finite non-negative weights with positive total")
        result = np.zeros_like(rgb)
        for branch, weight in zip(branches, weights):
            branch_rgb = rgb.copy()
            for child in branch.get("nodes", []):
                if not child.get("enabled", True): continue
                branch_rgb, ok, reason = _node_transform(branch_rgb, child)
                if not ok: raise ValueError(reason)
            result += branch_rgb * (weight/sum(weights))
        return _blend(rgb, result, strength), True, None
    if node_type in {"cube_lut", "lut"}:
        transformed = _sample_cube(rgb, _cube_from_node(node))
        return _blend(rgb, transformed, strength), True, None
    if node_type in {"matrix", "forward_matrix", "color_matrix", "camera_calibration"}:
        if node.get("camera_dependent"):
            raise ValueError("Camera calibration matrices cannot be applied to display RGB. Use CreativeInterpretation.")
        matrix = _matrix(node)
        effective = np.eye(3, dtype=np.float32) + strength * (matrix - np.eye(3, dtype=np.float32))
        return np.einsum("...c,dc->...d", rgb, effective), True, None
    if node_type in {"curve", "tone_curve", "profile_tone_curve"}:
        points = node.get("points") or node.get("curve") or node.get("data")
        transformed = np.stack([_curve_value(rgb[..., channel], points) for channel in range(3)], axis=-1)
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


def evaluate_graph(graph: dict, size: int = 17) -> tuple[CubeLUT, dict]:
    validate_color_graph(graph)
    if not 2 <= size <= 65:
        raise ValueError("Compiled graph cube size must be between 2 and 65")
    nodes = []
    for source_node in graph["nodes"]:
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
        values = np.clip(values, 0.0, 1.0)
        if not blendable:
            unsupported.append({"id": node_id, "type": node_type, "blendable": False, "reason": reason})
    if int(graph.get("base", 0)) == 1:
        gray = np.sum(values * np.array([.2126,.7152,.0722]), axis=-1, keepdims=True)
        values = np.repeat(gray, 3, axis=-1)
    if not np.isfinite(values).all():
        raise ValueError("Graph produced non-finite color values")
    unique_unsupported = {item["id"]: item for item in unsupported}
    cube = CubeLUT(str(graph.get("name", "Compiled graph")), size, (0.0, 0.0, 0.0),
                   (1.0, 1.0, 1.0), values.astype(np.float32, copy=False))
    report = graph_status(graph)
    interpretations=[]
    def collect(items):
        for n in items:
            if not n.get("enabled",True):continue
            if n.get("type") in {"dcp_creative","preset_creative"}:
                interpretations.append({"id":n.get("id"),"type":n["type"],"mode":n.get("mode","bounded_display"),"source_sha256":n.get("source_sha256"),"approximation":True})
            for branch in n.get("branches",[]):collect(branch.get("nodes",[]))
    collect(nodes)
    neutral=values[np.arange(size)*(size*size+size+1)]
    luminance=np.sum(neutral*np.array([.2126,.7152,.0722]),axis=-1)
    report.update({"engine":"source-aware-v2", "working_space":"display sRGB; source interpretations recorded explicitly",
                   "interpretations":interpretations,"black":values[0].tolist(),"white":values[-1].tolist(),
                   "gray_luminance_monotone":bool(np.all(np.diff(luminance)>=-1e-6)),
                   "compiled": True, "unsupported": list(unique_unsupported.values()),
                   "ready": report.get("ready", True) and not unique_unsupported})
    return cube, report


def compile_graph_cube(graph: dict, size: int = 17) -> tuple[bytes, dict]:
    cube, report = evaluate_graph(graph, size=size)
    if not report.get("ready"):
        raise ValueError("Cannot export incomplete Look: " + str(report.get("unsupported") or report.get("errors")))
    lines = [
        f'TITLE "{str(graph.get("name", "Compiled graph")).replace(chr(34), "")}"',
        f"LUT_3D_SIZE {cube.size}",
        "DOMAIN_MIN 0.0 0.0 0.0",
        "DOMAIN_MAX 1.0 1.0 1.0",
    ]
    lines.extend(" ".join(f"{float(value):.9f}" for value in row) for row in cube.values)
    return (("\n".join(lines) + "\n").encode("ascii"), report)