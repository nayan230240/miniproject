# Demo helpers: reset the fleet to a golden config, or poke one host live.
#
# Judges should not wait 30 seconds. After we change a fake server we
# immediately poll it so DriftWise updates on the next dashboard refresh.

from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from app.drift import detect_drift
from app.models import Server
from app.poller import fetch_config, fleet_urls, get_or_create_server, save_fingerprint, server_name_from_url
from app.database import SessionLocal

# Same baseline as docker-compose x-fleet-baseline (the "healthy" golden image).
GOLDEN_CONFIG = {
    "os_version": "Ubuntu 22.04.5 LTS",
    "kernel_version": "5.15.0-119-generic",
    "installed_packages": {
        "nginx": "1.18.0",
        "openssl": "3.0.2",
        "python3": "3.10.12",
        "curl": "7.81.0",
    },
    "open_ports": [22, 80, 443],
    "environment_variables": {
        "APP_ENV": "production",
        "LOG_LEVEL": "info",
        "TZ": "UTC",
    },
    "ssh_settings": {
        "PermitRootLogin": "no",
        "PasswordAuthentication": "no",
        "Port": "22",
    },
}


async def ingest_url(base_url: str) -> None:
    """Fetch /config from one fleet host and store a fingerprint now."""
    db = SessionLocal()
    try:
        async with httpx.AsyncClient() as client:
            config = await fetch_config(client, base_url)
        server = get_or_create_server(db, server_name_from_url(base_url), base_url)
        save_fingerprint(db, server, config)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def ingest_all() -> None:
    for url in fleet_urls():
        try:
            await ingest_url(url)
        except Exception as exc:
            print(f"[demo] poll failed for {url}: {exc}")


async def apply_golden_everywhere() -> None:
    """Make every simulated host identical (healthy fleet for the demo intro)."""
    async with httpx.AsyncClient() as client:
        for url in fleet_urls():
            response = await client.post(f"{url}/apply-config", json=GOLDEN_CONFIG, timeout=5.0)
            response.raise_for_status()
    await ingest_all()


def pick_healthy_server(db: Session, preferred_id: int | None) -> Server:
    """Prefer the server the judge clicked; otherwise the first majority host."""
    drift = detect_drift(db)
    majority_ids = [row["id"] for row in drift["majority"]["servers"]]
    if preferred_id is not None:
        server = db.get(Server, preferred_id)
        if server is None:
            raise ValueError(f"Server {preferred_id} not found")
        if preferred_id in majority_ids:
            return server
        # Selected host is already drifted; fall through to a healthy one.
    if not majority_ids:
        raise ValueError("No healthy (majority) server left to drift")
    server = db.get(Server, majority_ids[0])
    if server is None:
        raise ValueError("Majority server row is missing")
    return server


async def simulate_live_drift(db: Session, server_id: int | None) -> dict:
    """
    1. POST /simulate-drift on a healthy fake host (opens port 31337, root SSH).
    2. Poll that host immediately.
    3. Return the new drift view so the UI can jump to it.
    """
    target = pick_healthy_server(db, server_id)
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{target.base_url}/simulate-drift", timeout=5.0)
        response.raise_for_status()
        applied = response.json()
    await ingest_url(target.base_url)
    db.expire_all()
    drift = detect_drift(db)
    outlier = next((item for item in drift["outliers"] if item["server_id"] == target.id), None)
    return {
        "ok": True,
        "server_id": target.id,
        "name": target.name,
        "changes": applied.get("changes", []),
        "outlier": outlier,
        "drift": drift,
    }
