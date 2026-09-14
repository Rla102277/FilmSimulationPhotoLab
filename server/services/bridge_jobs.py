from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
import uuid

from sqlalchemy import text

from core.leica.authoritative import get_authoritative_look
from server.db.database import engine


JOB_TYPES = {
    "LEICA_READ_LOOKS",
    "LEICA_INSTALL_LOOK",
    "LEICA_VERIFY_LOOK",
    "LEICA_INSTALL_PACK",
    "FUJI_STATUS",
    "FUJI_PROCESS_RAW",
}
WRITE_JOB_TYPES = {"LEICA_INSTALL_LOOK", "LEICA_INSTALL_PACK", "FUJI_PROCESS_RAW"}
TRANSITIONS = {
    "QUEUED": {"BRIDGE_RECEIVED", "CANCELLED"},
    "BRIDGE_RECEIVED": {"CAMERA_CONNECTED", "FAILED"},
    "CAMERA_CONNECTED": {"VALIDATING", "FAILED"},
    "VALIDATING": {"RUNNING", "FAILED"},
    "RUNNING": {"VERIFYING", "FAILED"},
    "VERIFYING": {"SUCCESS", "FAILED"},
}


def _secret() -> bytes:
    value = os.getenv("SESSION_SECRET")
    if not value:
        raise RuntimeError("SESSION_SECRET is required for bridge authentication")
    return value.encode()


def _token_hash(token: str) -> str:
    return hmac.new(_secret(), token.encode(), hashlib.sha256).hexdigest()


def create_pairing_ticket(ttl_seconds: int = 300) -> str:
    expires = int(time.time()) + ttl_seconds
    nonce = secrets.token_urlsafe(12)
    body = f"{expires}.{nonce}"
    signature = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def verify_pairing_ticket(ticket: str) -> None:
    try:
        expires_text, nonce, signature = ticket.split(".", 2)
        body = f"{expires_text}.{nonce}"
        expected = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        if int(expires_text) < int(time.time()):
            raise PermissionError("Pairing ticket expired")
    except PermissionError:
        raise
    except (ValueError, TypeError) as exc:
        raise PermissionError("Invalid pairing ticket") from exc


def register_bridge(name: str, capabilities: dict, version: str, pairing_ticket: str) -> dict:
    verify_pairing_ticket(pairing_ticket)
    bridge_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(32)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO bridges(id,name,token_hash,capabilities,version) "
                "VALUES(:id,:name,:token_hash,CAST(:capabilities AS jsonb),:version)"
            ),
            {
                "id": bridge_id,
                "name": name,
                "token_hash": _token_hash(token),
                "capabilities": json.dumps(capabilities),
                "version": version,
            },
        )
    return {"id": bridge_id, "token": token, "note": "Store this token locally; it is shown only once."}


def authenticate_bridge(token: str) -> dict:
    hashed = _token_hash(token)
    with engine.begin() as connection:
        row = connection.execute(
            text("SELECT id,name,capabilities,version FROM bridges WHERE token_hash=:token_hash"),
            {"token_hash": hashed},
        ).mappings().first()
        if not row:
            raise PermissionError("Invalid bridge token")
        connection.execute(text("UPDATE bridges SET last_seen=NOW() WHERE id=:id"), {"id": row["id"]})
    return dict(row)


def create_job(job_type: str, payload: dict, bridge_id: str | None = None) -> dict:
    if job_type not in JOB_TYPES:
        raise ValueError("Unsupported bridge job type")
    if job_type.startswith("LEICA_") and job_type != "LEICA_READ_LOOKS":
        look_id = int(payload.get("look_id", 0))
        look = get_authoritative_look(look_id)
        if payload.get("look_name") != look["name"]:
            raise ValueError("Look name does not match the authoritative manifest")
        if payload.get("artifact_sha256") != look["cube_sha256"]:
            raise ValueError("Artifact checksum does not match the authoritative CUBE")
        if payload.get("target_camera") not in {"LEICA_Q3", "LEICA_Q3_43"}:
            raise ValueError("Unsupported Leica target camera")
    job_id = str(uuid.uuid4())
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO bridge_jobs(id,bridge_id,job_type,status,payload) "
                "VALUES(:id,:bridge_id,:job_type,'QUEUED',CAST(:payload AS jsonb))"
            ),
            {"id": job_id, "bridge_id": bridge_id, "job_type": job_type, "payload": json.dumps(payload)},
        )
    return get_job(job_id)


def get_job(job_id: str) -> dict:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT * FROM bridge_jobs WHERE id=:id"), {"id": job_id}
        ).mappings().first()
    if not row:
        raise KeyError("Bridge job not found")
    return dict(row)


def claim_next_job(bridge_id: str) -> dict | None:
    with engine.begin() as connection:
        row = connection.execute(
            text(
                "SELECT * FROM bridge_jobs WHERE status='QUEUED' "
                "AND (bridge_id IS NULL OR bridge_id=:bridge_id) "
                "ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1"
            ),
            {"bridge_id": bridge_id},
        ).mappings().first()
        if not row:
            return None
        connection.execute(
            text(
                "UPDATE bridge_jobs SET bridge_id=:bridge_id,status='BRIDGE_RECEIVED',updated_at=NOW() "
                "WHERE id=:id"
            ),
            {"bridge_id": bridge_id, "id": row["id"]},
        )
    return get_job(row["id"])


def transition_job(
    job_id: str,
    new_status: str,
    result: dict | None = None,
    error: str | None = None,
    bridge_id: str | None = None,
) -> dict:
    current = get_job(job_id)
    if bridge_id is not None and current["bridge_id"] != bridge_id:
        raise PermissionError("Bridge does not own this job")
    if new_status not in TRANSITIONS.get(current["status"], set()):
        raise ValueError(f"Invalid job transition {current['status']} -> {new_status}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE bridge_jobs SET status=:status,result=CAST(:result AS jsonb),"
                "error=:error,updated_at=NOW() WHERE id=:id"
            ),
            {
                "status": new_status,
                "result": json.dumps(result) if result is not None else None,
                "error": error,
                "id": job_id,
            },
        )
    return get_job(job_id)


def add_log(job_id: str, level: str, message: str, detail: dict) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO bridge_logs(job_id,level,message,detail) "
                "VALUES(:job_id,:level,:message,CAST(:detail AS jsonb))"
            ),
            {"job_id": job_id, "level": level, "message": message, "detail": json.dumps(detail)},
        )