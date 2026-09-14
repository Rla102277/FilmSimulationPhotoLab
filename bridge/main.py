"""Small outbound-only IA Camera Bridge client.

Run this on the local Mac, never in the Replit workflow. Hardware transports are
separate adapters; this client only handles authenticated server communication.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


def request(server: str, path: str, method: str = "POST", token: str | None = None, body: dict | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = json.dumps(body or {}).encode()
    call = urllib.request.Request(server.rstrip("/") + path, data=payload, headers=headers, method=method)
    with urllib.request.urlopen(call, timeout=20) as response:
        return json.loads(response.read() or b"{}")


def register(config: dict, pairing_ticket: str) -> str:
    result = request(
        config["serverUrl"],
        "/api/bridge/register",
        body={
            "name": config["bridgeName"],
            "version": config.get("version", "0.1.0"),
            "capabilities": config.get("capabilities", {}),
            "pairing_ticket": pairing_ticket,
        },
    )
    return result["token"]


def handle_job(server: str, token: str, job: dict) -> None:
    job_id = job["id"]
    request(server, f"/api/bridge/jobs/{job_id}/logs", token=token, body={
        "level": "INFO",
        "message": "Bridge received job",
        "detail": {"job_type": job["job_type"]},
    })
    request(server, f"/api/bridge/jobs/{job_id}/transition", token=token, body={"status": "CAMERA_CONNECTED"})
    request(server, f"/api/bridge/jobs/{job_id}/transition", token=token, body={"status": "VALIDATING"})
    request(
        server,
        f"/api/bridge/jobs/{job_id}/transition",
        token=token,
        body={
            "status": "FAILED",
            "error": "No hardware transport adapter is configured. The bridge refused to simulate camera execution.",
        },
    )


def run(config_path: Path, once: bool) -> None:
    config = json.loads(config_path.read_text())
    token = config.get("bridgeToken")
    if not token:
        raise SystemExit("bridgeToken is missing. Generate a short-lived pairing ticket in Photo Lab and register first.")
    while True:
        request(config["serverUrl"], "/api/bridge/heartbeat", token=token)
        result = request(config["serverUrl"], "/api/bridge/jobs/claim", token=token)
        if result.get("job"):
            handle_job(config["serverUrl"], token, result["job"])
        if once:
            return
        time.sleep(max(5, int(config.get("pollSeconds", 10))))


def main() -> None:
    parser = argparse.ArgumentParser(description="IA Camera Bridge outbound client")
    parser.add_argument("--config", default="bridge/local_config.json")
    parser.add_argument("--pairing-ticket")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    path = Path(args.config)
    config = json.loads(path.read_text())
    if args.pairing_ticket:
        print(register(config, args.pairing_ticket))
        return
    run(path, args.once)


if __name__ == "__main__":
    main()
