from __future__ import annotations

import base64
import os
from functools import lru_cache

import jwt
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from jwt import PyJWKClient


proxy_router = APIRouter()


def _frontend_api() -> str:
    key = os.getenv("CLERK_PUBLISHABLE_KEY", "")
    encoded = key.split("_", 2)[-1]
    try:
        host = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode().rstrip("$")
    except Exception as exc:
        raise RuntimeError("Invalid Clerk publishable key") from exc
    return f"https://{host}"


@lru_cache(maxsize=1)
def _proxy_url(request: Request) -> str:
    forwarded_host = request.headers.get("x-forwarded-host", "").split(",")[0].strip()
    host = forwarded_host or request.headers.get("host", "").strip()
    protocol = request.headers.get("x-forwarded-proto", "https").split(",")[0].strip()
    return f"{protocol}://{host}/api/__clerk"


@lru_cache(maxsize=8)
def _jwks(proxy_url: str) -> PyJWKClient:
    return PyJWKClient(
        "https://frontend-api.clerk.dev/.well-known/jwks.json",
        headers={
            "Clerk-Proxy-Url": proxy_url,
            "Clerk-Secret-Key": os.environ["CLERK_SECRET_KEY"],
        },
        cache_keys=True,
    )


def require_user(request: Request) -> str:
    token = request.cookies.get("__session")
    authorization = request.headers.get("authorization", "")
    if not token and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Sign in required")
    try:
        key = _jwks(_proxy_url(request)).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token, key.key, algorithms=["RS256"],
            options={"verify_aud": False, "verify_iss": False},
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from exc
    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Session has no user identity")
    return str(user_id)


@proxy_router.api_route("/api/__clerk/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def clerk_proxy(path: str, request: Request):
    target = f"https://frontend-api.clerk.dev/{path}"
    headers = {
        key: value for key, value in request.headers.items()
        if key.lower() not in {"host", "content-length"}
    }
    headers["Clerk-Proxy-Url"] = _proxy_url(request)
    headers["Clerk-Secret-Key"] = os.environ["CLERK_SECRET_KEY"]
    async with httpx.AsyncClient(follow_redirects=False, timeout=30) as client:
        upstream = await client.request(
            request.method, target, params=request.query_params,
            content=await request.body(), headers=headers,
        )
    response = Response(upstream.content, status_code=upstream.status_code)
    for key, value in upstream.headers.multi_items():
        if key.lower() not in {"content-length", "content-encoding", "transfer-encoding", "connection"}:
            response.headers.append(key, value)
    return response