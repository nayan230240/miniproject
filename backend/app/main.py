
from __future__ import annotations

import asyncio
import hashlib
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import Base, engine, SessionLocal, get_db
from app.models import Server, Fingerprint, Baseline
from app.drift import detect_drift
from app.explain import explain_server
from app.demo import apply_golden_everywhere, simulate_live_drift
from app.poller import poll_loop


# --------------------------------------------------
# BASELINE CONFIGURATION
# --------------------------------------------------

BASELINE_CATEGORIES = {
    "os_version": "os_version",
    "kernel_version": "kernel_version",
    "installed_packages": "installed_packages",
    "open_ports": "open_ports",
    "environment_variables": "environment_variables",
    "ssh_settings": "ssh_settings",
}


def normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return a consistent JSON-compatible configuration."""
    return json.loads(
        json.dumps(config, sort_keys=True, default=str)
    )


def calculate_category_hashes(
    config: dict[str, Any]
) -> dict[str, str]:
    """Calculate SHA-256 hashes for each configuration category."""
    hashes = {}

    for category, config_key in BASELINE_CATEGORIES.items():
        value = config.get(config_key)

        canonical_value = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            default=str
        )

        hashes[category] = hashlib.sha256(
            canonical_value.encode("utf-8")
        ).hexdigest()

    return hashes


def baseline_to_dict(baseline: Baseline | None) -> dict:
    if baseline is None:
        return {
            "configured": False,
            "config": None,
            "created_at": None,
            "updated_at": None,
            "notes": None,
        }

    return {
        "configured": True,
        "config": baseline.normalized_config,
        "created_at": baseline.created_at,
        "updated_at": baseline.updated_at,
        "notes": baseline.notes,
    }


# --------------------------------------------------
# REQUEST MODELS
# --------------------------------------------------

class BaselineBody(BaseModel):
    config: dict[str, Any] = Field(
        ...,
        description="Approved original server configuration"
    )
    notes: str | None = None
    replace: bool = False


class SimulateBody(BaseModel):
    server_id: int | None = None


# --------------------------------------------------
# APPLICATION LIFECYCLE
# --------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    poller_task = asyncio.create_task(poll_loop())

    yield

    poller_task.cancel()

    try:
        await poller_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Configo - AI Server Drift Detector",
    description=(
        "Detect server configuration drift using majority "
        "comparison, approved baseline verification, and Gemini AI."
    ),
    version="2.0.0",
    lifespan=lifespan,
)


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# SERIALIZATION HELPERS
# --------------------------------------------------

def fingerprint_to_dict(fingerprint: Fingerprint) -> dict:
    return {
        "id": fingerprint.id,
        "server_id": fingerprint.server_id,
        "collected_at": fingerprint.collected_at,
        "full_hash": fingerprint.full_hash,
        "os_version_hash": fingerprint.os_version_hash,
        "kernel_version_hash": fingerprint.kernel_version_hash,
        "packages_hash": fingerprint.packages_hash,
        "ports_hash": fingerprint.ports_hash,
        "env_vars_hash": fingerprint.env_vars_hash,
        "ssh_hash": fingerprint.ssh_hash,
        "normalized_config": fingerprint.normalized_config,
    }


def server_to_dict(server: Server) -> dict:
    latest = (
        server.fingerprints[0]
        if server.fingerprints
        else None
    )

    return {
        "id": server.id,
        "name": server.name,
        "base_url": server.base_url,
        "last_seen_at": server.last_seen_at,
        "latest_fingerprint": (
            fingerprint_to_dict(latest)
            if latest
            else None
        ),
    }


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "application": "Configo",
        "version": "2.0.0",
    }


# --------------------------------------------------
# SERVER ENDPOINTS
# --------------------------------------------------

@app.get("/servers")
def get_servers(db: Session = Depends(get_db)):
    servers = db.query(Server).order_by(Server.id).all()

    return [
        server_to_dict(server)
        for server in servers
    ]


@app.get("/servers/{server_id}/fingerprints")
def get_server_fingerprints(
    server_id: int,
    db: Session = Depends(get_db)
):
    server = db.query(Server).filter(
        Server.id == server_id
    ).first()

    if server is None:
        raise HTTPException(
            status_code=404,
            detail="Server not found"
        )

    return [
        fingerprint_to_dict(item)
        for item in server.fingerprints
    ]


# --------------------------------------------------
# APPROVED BASELINE ENDPOINTS
# --------------------------------------------------

@app.get("/baseline")
def get_baseline(db: Session = Depends(get_db)):
    """
    Return the currently approved original baseline.

    Reading the baseline never changes it.
    """
    baseline = db.get(Baseline, 1)

    return baseline_to_dict(baseline)


@app.post("/baseline/capture")
def capture_baseline(
    body: BaselineBody,
    db: Session = Depends(get_db)
):
    """
    Save an explicitly supplied approved configuration.

    The existing baseline cannot be overwritten unless
    replace=true is explicitly supplied.
    """
    config = normalize_config(body.config)

    if not config:
        raise HTTPException(
            status_code=400,
            detail="Baseline configuration cannot be empty."
        )

    for key in BASELINE_CATEGORIES.values():
        if key not in config:
            raise HTTPException(
                status_code=400,
                detail=f"Missing baseline configuration category: {key}"
            )

    existing = db.get(Baseline, 1)

    if existing is not None and not body.replace:
        raise HTTPException(
            status_code=409,
            detail=(
                "An approved baseline already exists. "
                "Set replace=true only when you intentionally "
                "want to replace the approved baseline."
            )
        )

    now = datetime.now(timezone.utc)

    if existing is None:
        baseline = Baseline(
            id=1,
            normalized_config=config,
            category_hashes=calculate_category_hashes(config),
            created_at=now,
            updated_at=now,
            notes=body.notes,
        )
        db.add(baseline)

    else:
        existing.normalized_config = config
        existing.category_hashes = calculate_category_hashes(config)
        existing.updated_at = now
        existing.notes = body.notes

    db.commit()

    saved_baseline = db.get(Baseline, 1)

    return {
        "message": (
            "Approved baseline saved successfully."
            if existing is None
            else "Approved baseline replaced successfully."
        ),
        "baseline": baseline_to_dict(saved_baseline),
    }


@app.delete("/baseline")
def delete_baseline(db: Session = Depends(get_db)):
    """
    Explicitly delete the approved baseline.

    This does not delete server fingerprints.
    """
    baseline = db.get(Baseline, 1)

    if baseline is None:
        raise HTTPException(
            status_code=404,
            detail="No baseline is currently configured."
        )

    db.delete(baseline)
    db.commit()

    return {
        "message": "Approved baseline deleted."
    }


# --------------------------------------------------
# DRIFT DETECTION
# --------------------------------------------------

@app.get("/drift")
def get_drift(db: Session = Depends(get_db)):
    """
    Compare:
    1. Every server against the current majority.
    2. Every server against the approved baseline.
    3. The majority configuration against the baseline.
    """
    return detect_drift(db)


@app.get("/drift/{server_id}/explanation")
def get_drift_explanation(
    server_id: int,
    db: Session = Depends(get_db)
):
    server = db.query(Server).filter(
        Server.id == server_id
    ).first()

    if server is None:
        raise HTTPException(
            status_code=404,
            detail="Server not found"
        )

    try:
        return explain_server(db, server_id)

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to generate explanation: {str(error)}"
        )


# --------------------------------------------------
# DEMO ENDPOINTS
# --------------------------------------------------

@app.post("/simulate-drift")
async def simulate_drift(
    body: SimulateBody,
    db: Session = Depends(get_db)
):
    try:
        result = await simulate_live_drift(
            db,
            body.server_id
        )

        return result

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to simulate drift: {str(error)}"
        )


@app.post("/demo/reset")
async def reset_demo():
    """
    Reset all simulated fleet servers to the demo golden config.

    IMPORTANT:
    This does not capture, update, or replace the approved baseline.
    """
    try:
        await apply_golden_everywhere()

        return {
            "message": (
                "Demo fleet configuration reset successfully. "
                "The approved baseline was not changed."
            )
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to reset demo fleet: {str(error)}"
        )
