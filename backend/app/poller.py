
# Background poller.
# Reads the polling interval from database settings when available.
# Falls back to POLL_INTERVAL_SECONDS (default 30).

import asyncio
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from sqlalchemy import select

from app.database import SessionLocal
from app.fingerprint import fingerprint_config
from app.models import AppSetting, Fingerprint, Server


DEFAULT_FLEET_URLS = ",".join(
    f"http://localhost:{port}" for port in range(8001, 8006)
)


def fleet_urls() -> list[str]:
    raw = os.getenv("FLEET_URLS", DEFAULT_FLEET_URLS)
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


def poll_interval_seconds() -> int:
    """
    Read the saved polling interval from SQLite.
    Fall back to the environment variable if no saved setting exists.
    """
    default_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))

    db = SessionLocal()
    try:
        setting = db.get(AppSetting, "poll_interval_seconds")

        if setting is not None:
            try:
                interval = int(setting.value)
                return max(10, min(interval, 3600))
            except (TypeError, ValueError):
                pass

        return max(10, min(default_interval, 3600))

    except Exception as exc:
        print(f"[poller] could not read settings: {exc}")
        return max(10, min(default_interval, 3600))

    finally:
        db.close()


def server_name_from_url(base_url: str) -> str:
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
        db.flush()
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
                    print(
                        f"[poller] could not poll {name} "
                        f"({base_url}): {exc}"
                    )

    finally:
        db.close()


async def poll_loop() -> None:
    """
    Run continuously until the FastAPI application shuts down.

    The interval is re-read from the database after every polling cycle,
    so changes made in Settings take effect without restarting the app.
    """
    print(f"[poller] starting; targets={fleet_urls()}")

    while True:
        await poll_once()

        interval = poll_interval_seconds()
        print(f"[poller] next scan in {interval} seconds")

        await asyncio.sleep(interval)
