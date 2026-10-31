# Configo API entry point.
# Run locally: uvicorn app.main:app --reload
# Open docs at: http://localhost:8000/docs
#
# Endpoints:
#   GET /health
#   GET /servers
#   GET /servers/{id}/fingerprints
#   GET /drift
#   GET /drift/{server_id}/explanation
#   POST /simulate-drift
#   POST /demo/reset

from contextlib import asynccontextmanager

import asyncio

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from pydantic import BaseModel, Field

from app.database import Base, engine, get_db
from app.demo import apply_golden_everywhere, simulate_live_drift
from app.drift import detect_drift
from app.explain import explain_server
from app.models import Fingerprint, Server
from app.poller import poll_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1) Make sure SQLite tables exist.
    Base.metadata.create_all(bind=engine)
    # 2) Start the 30-second fleet poller in the background.
    task = asyncio.create_task(poll_loop())
    yield
    # 3) Stop the poller when Uvicorn shuts down.
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Configo",
    description="AI-powered configuration drift detector.",
    version="0.0.1",
    lifespan=lifespan,
)

# The React app runs on another port, so we allow browser requests from anywhere for now.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def fingerprint_to_dict(row: Fingerprint) -> dict:
    """Turn a database row into JSON for the API."""
    return {
        "id": row.id,
        "server_id": row.server_id,
        "collected_at": row.collected_at.isoformat() if row.collected_at else None,
        "full_hash": row.full_hash,
        "category_hashes": {
            "os_version": row.os_version_hash,
            "kernel_version": row.kernel_version_hash,
            "installed_packages": row.packages_hash,
            "open_ports": row.ports_hash,
            "environment_variables": row.env_vars_hash,
            "ssh_settings": row.ssh_hash,
        },
        "normalized_config": row.normalized_config,
    }


def server_to_dict(server: Server, latest: Fingerprint | None = None) -> dict:
    return {
        "id": server.id,
        "name": server.name,
        "base_url": server.base_url,
        "last_seen_at": server.last_seen_at.isoformat() if server.last_seen_at else None,
        "latest_fingerprint": fingerprint_to_dict(latest) if latest else None,
    }


@app.get("/health")
def health():
    """Simple liveness check used by Docker and by you in the browser."""
    return {"status": "ok", "service": "configo-backend"}


@app.get("/servers")
def list_servers(db: Session = Depends(get_db)):
    """
    List every fleet server we have seen, plus its newest fingerprint.
    Empty until the poller has completed at least one successful fetch.
    """
    servers = db.scalars(select(Server).order_by(Server.id)).all()
    result = []
    for server in servers:
        latest = db.scalar(
            select(Fingerprint)
            .where(Fingerprint.server_id == server.id)
            .order_by(Fingerprint.collected_at.desc(), Fingerprint.id.desc())
        )
        result.append(server_to_dict(server, latest))
    return result


@app.get("/servers/{server_id}/fingerprints")
def list_fingerprints(server_id: int, db: Session = Depends(get_db)):
    """Return the fingerprint history for one server (newest first)."""
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail=f"Server {server_id} not found")

    rows = db.scalars(
        select(Fingerprint)
        .where(Fingerprint.server_id == server_id)
        .order_by(Fingerprint.collected_at.desc(), Fingerprint.id.desc())
    ).all()
    return {
        "server": server_to_dict(server),
        "fingerprints": [fingerprint_to_dict(row) for row in rows],
    }


@app.get("/drift")
def get_drift(db: Session = Depends(get_db)):
    """
    Group servers by config similarity and list outliers.

    Uses the newest fingerprint for each server. See app/drift.py for
    the DBSCAN explanation.
    """
    return detect_drift(db)


@app.get("/drift/{server_id}/explanation")
def get_drift_explanation(server_id: int, db: Session = Depends(get_db)):
    """
    Ask an LLM to narrate one server's drift in plain language.

    If the API key is missing or the vendor call fails, a fallback summary
    is returned instead of an error. See app/explain.py.
    """
    try:
        return explain_server(db, server_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class SimulateBody(BaseModel):
    # Optional: which host to poke. If omitted (or already drifted), we pick a healthy one.
    server_id: int | None = Field(default=None)


@app.post("/simulate-drift")
async def post_simulate_drift(body: SimulateBody = SimulateBody(), db: Session = Depends(get_db)):
    """
    Change one fake server's config *right now*, then poll it so detection
    does not wait for the 30-second timer. Used by the DriftWise button.
    """
    try:
        return await simulate_live_drift(db, body.server_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach fleet host: {exc}") from exc


@app.post("/demo/reset")
async def post_demo_reset():
    """Put every fleet host back on the golden config (healthy fleet)."""
    try:
        await apply_golden_everywhere()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Demo reset failed: {exc}") from exc
    return {"ok": True, "message": "All fleet hosts reset to the golden baseline"}
