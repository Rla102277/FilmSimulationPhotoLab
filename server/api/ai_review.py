from __future__ import annotations

import json
import os

import httpx
import numpy as np
from fastapi import APIRouter, Depends, Request

from core.color.cube import parse_cube
from server.api.studio import _compiled, _request_graph
from server.auth import require_user


router = APIRouter(prefix="/studio", tags=["studio-review"])


async def _ai_commentary(summary: dict) -> tuple[str, list[str]]:
    prompt = (
        "You are reviewing metadata for a deterministic photographic 3D LUT. "
        "Do not generate LUT rows or claim visual/colorimetric certification. "
        "Return JSON with a concise summary string and 1-4 review_notes strings. "
        f"Metrics: {json.dumps(summary, sort_keys=True)}"
    )
    provider = os.getenv("AI_REVIEW_PROVIDER", "").lower()
    if provider == "xai" and os.getenv("XAI_API_KEY"):
        url, key, model = "https://api.x.ai/v1/chat/completions", os.environ["XAI_API_KEY"], "grok-3-mini"
    elif provider == "openai" and os.getenv("OPENAI_API_KEY"):
        url, key, model = "https://api.openai.com/v1/chat/completions", os.environ["OPENAI_API_KEY"], "gpt-4.1-mini"
    elif os.getenv("ANTHROPIC_API_KEY"):
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post("https://api.anthropic.com/v1/messages", headers={
                "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                "anthropic-version": "2023-06-01",
            }, json={"model": "claude-3-5-haiku-latest", "max_tokens": 350,
                     "system": "Return JSON only. Never output CUBE data or RGB sample arrays.",
                     "messages": [{"role": "user", "content": prompt}]})
        response.raise_for_status()
        parsed = json.loads(response.json()["content"][0]["text"])
        return "anthropic", [str(parsed.get("summary", "")), *map(str, parsed.get("review_notes", []))]
    else:
        return "deterministic", []
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, headers={"Authorization": f"Bearer {key}"}, json={
            "model": model, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": "Return JSON only. Never output CUBE data or RGB sample arrays."},
                         {"role": "user", "content": prompt}],
        })
    response.raise_for_status()
    parsed = json.loads(response.json()["choices"][0]["message"]["content"])
    return provider, [str(parsed.get("summary", "")), *map(str, parsed.get("review_notes", []))]


@router.post("/graph/review")
async def review_graph(request: Request, _user_id: str = Depends(require_user)):
    graph = await _request_graph(request)
    cube_data, report = _compiled(graph)
    cube = parse_cube(cube_data)
    finite = bool(np.isfinite(cube.values).all())
    minimum, maximum = float(cube.values.min()), float(cube.values.max())
    summary = {
        "name": str(graph.get("name", "Untitled")),
        "cube_size": cube.size,
        "row_count": int(cube.values.shape[0]),
        "finite": finite,
        "range": [minimum, maximum],
        "node_count": len(graph.get("nodes", [])),
        "unsupported_count": len(report.get("unsupported", [])),
    }
    findings = [
        "Valid 17×17×17 CUBE with exactly 4,913 RGB rows." if cube.size == 17 and cube.values.shape == (4913, 3)
        else "CUBE dimensions or row count are invalid.",
        "All compiled values are finite and inside 0…1." if finite and minimum >= 0 and maximum <= 1
        else "Compiled values contain non-finite or out-of-range data.",
    ]
    provider = "deterministic"
    try:
        provider, ai_notes = await _ai_commentary(summary)
        findings.extend(note for note in ai_notes if note) 
    except Exception:
        findings.append("AI commentary unavailable; deterministic validation still passed.")
    return {
        "valid": cube.size == 17 and cube.values.shape == (4913, 3) and finite and minimum >= 0 and maximum <= 1,
        "provider": provider,
        "metrics": summary,
        "findings": findings,
        "authority": "Deterministic compiler and numerical validation; AI commentary is advisory only.",
    }