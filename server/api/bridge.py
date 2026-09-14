from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from server.services.bridge_jobs import (
    add_log,
    authenticate_bridge,
    claim_next_job,
    create_pairing_ticket,
    register_bridge,
    transition_job,
)


router = APIRouter(prefix="/bridge", tags=["camera-bridge"])


class BridgeRegistration(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(default="", max_length=60)
    capabilities: dict = Field(default_factory=dict)
    pairing_ticket: str


class JobTransition(BaseModel):
    status: str
    result: dict | None = None
    error: str | None = Field(default=None, max_length=2000)


class JobLog(BaseModel):
    level: str = Field(pattern="^(DEBUG|INFO|WARNING|ERROR)$")
    message: str = Field(min_length=1, max_length=2000)
    detail: dict = Field(default_factory=dict)


def current_bridge(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bridge bearer token required")
    try:
        return authenticate_bridge(authorization.removeprefix("Bearer ").strip())
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/register", status_code=201)
def register(body: BridgeRegistration):
    try:
        return register_bridge(body.name, body.capabilities, body.version, body.pairing_ticket)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/pairing-ticket")
def pairing_ticket():
    return {"ticket": create_pairing_ticket(), "expires_in_seconds": 300}


@router.post("/heartbeat")
def heartbeat(bridge: dict = Depends(current_bridge)):
    return {"ok": True, "bridge": bridge}


@router.post("/jobs/claim")
def claim(bridge: dict = Depends(current_bridge)):
    return {"job": claim_next_job(bridge["id"])}


@router.post("/jobs/{job_id}/transition")
def transition(job_id: str, body: JobTransition, bridge: dict = Depends(current_bridge)):
    try:
        return transition_job(job_id, body.status, body.result, body.error, bridge["id"])
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/logs", status_code=204)
def log(job_id: str, body: JobLog, bridge: dict = Depends(current_bridge)):
    add_log(job_id, body.level, body.message, body.detail)