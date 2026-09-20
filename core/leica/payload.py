from __future__ import annotations

from core.leica.authoritative import get_authoritative_look, read_look_asset
from core.leica.compiler import compile_look_payload
from core.leica.parser import parse_look_payload


def build_authoritative_payload(look_id: int, marker: int = 0x20000014) -> bytes:
    look = get_authoritative_look(look_id)
    cube = read_look_asset(look_id, "cube")
    icon = read_look_asset(look_id, "icon")
    payload, _ = compile_look_payload(look["id"], look["name"], icon, cube, 2, look["base"], marker)
    return payload


def inspect_payload(payload: bytes) -> dict:
    return parse_look_payload(payload)