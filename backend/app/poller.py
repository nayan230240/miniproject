# Background poller.
# Every POLL_INTERVAL_SECONDS (default 30) it:
#   1. GET /config from each fleet URL
#   2. Builds SHA-256 fingerprints
#   3. Saves a new row in SQLite with a timestamp
#
# Failures are logged and skipped so one down host does not stop the others.

import asyncio
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from sqlalchemy import select

from app.database import SessionLocal
from app.fingerprint import fingerprint_config
from app.models import Fingerprint, Server

# Comma-separated list, e.g. http://fleet-1:8000,http://fleet-2:8000
# Inside Docker, service names are DNS names on the compose network.
DEFAULT_FLEET_URLS = ",".join(
    f"http://localhost:{port}" for port in range(8001, 8006)
)


def fleet_urls() -> list[str]:
    raw = os.getenv("FLEET_URLS", DEFAULT_FLEET_URLS)
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


def poll_interval_seconds() -> int:
    return int(os.getenv("POLL_INTERVAL_SECONDS", "30"))


def server_name_from_url(base_url: str) -> str:
    """http://fleet-1:8000 -> fleet-1   (or localhost-8001 when run locally)."""
    parsed = urlparse(base_url)
    host = parsed.hostname or "unknown"
    if host in {"localhost", "127.0.0.1"} and parsed.port:
        return f"{host}-{parsed.port}"
    return host


def get_or_create_server(db, name: str, base_url: str) -> Server:
    server = db.scalar(select(Server).where(Server.name == name))
    if server is None:
        server = Server(name=name, base_url=base_url)
        db.add(server)
        db.flush()  # assign an id before we insert fingerprints
    else:
        server.base_url = base_url
    return server


def save_fingerprint(db, server: Server, config: dict) -> Fingerprint:
    hashes = fingerprint_config(config)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row = Fingerprint(
        server_id=server.id,
        collected_at=now,
        **hashes,
    )
    server.last_seen_at = now
    db.add(row)
    return row


async def fetch_config(client: httpx.AsyncClient, base_url: str) -> dict:
    response = await client.get(f"{base_url}/config", timeout=5.0)
    response.raise_for_status()
    return response.json()


async def poll_once() -> None:
    """One full pass over every fleet server."""
    db = SessionLocal()
    try:
        async with httpx.AsyncClient() as client:
            for base_url in fleet_urls():
                name = server_name_from_url(base_url)
                try:
                    config = await fetch_config(client, base_url)
                    server = get_or_create_server(db, name, base_url)
                    save_fingerprint(db, server, config)
                    db.commit()
                    print(f"[poller] saved fingerprint for {name}")
                except Exception as exc:
                    db.rollback()
                    print(f"[poller] could not poll {name} ({base_url}): {exc}")
    finally:
        db.close()


async def poll_loop() -> None:
    """Run forever until the FastAPI app shuts down (task is cancelled)."""
    interval = poll_interval_seconds()
    print(f"[poller] starting; interval={interval}s targets={fleet_urls()}")
    while True:
        await poll_once()
        await asyncio.sleep(interval)
