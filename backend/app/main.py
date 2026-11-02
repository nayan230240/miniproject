
from __future__ import annotations

import asyncio
import hashlib
import json
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import Base, engine, SessionLocal, get_db
from app.models import Server, Fingerprint, Baseline, AppSetting
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
# HISTORY HELPERS
# --------------------------------------------------

def canonical_value(value: Any) -> str:
    """Create a stable representation of a category value."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str
    )


def build_history_events(
    db: Session,
    server_id: int | None = None,
    category: str | None = None,
) -> list[dict]:
    """
    Build historical events by comparing consecutive fingerprints.
    """

    query = (
        db.query(Fingerprint, Server.name)
        .join(Server, Fingerprint.server_id == Server.id)
    )

    if server_id is not None:
        query = query.filter(
            Fingerprint.server_id == server_id
        )

    fingerprints = query.order_by(
        Fingerprint.server_id.asc(),
        Fingerprint.collected_at.asc(),
        Fingerprint.id.asc()
    ).all()

    previous_configs: dict[int, dict] = {}
    seen_values: dict[int, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )

    events = []

    for fingerprint, server_name in fingerprints:
        current_config = fingerprint.normalized_config or {}

        if isinstance(current_config, str):
            try:
                current_config = json.loads(current_config)
            except (json.JSONDecodeError, TypeError):
                current_config = {}

        if not isinstance(current_config, dict):
            current_config = {}

        current_config = normalize_config(current_config)

        current_server_id = fingerprint.server_id
        previous_config = previous_configs.get(current_server_id)

        if previous_config is None:
            for category_name, config_key in BASELINE_CATEGORIES.items():
                if config_key in current_config:
                    seen_values[current_server_id][category_name].add(
                        canonical_value(current_config[config_key])
                    )

            previous_configs[current_server_id] = current_config
            continue

        for category_name, config_key in BASELINE_CATEGORIES.items():

            if category is not None and category_name != category:
                continue

            previous_value = previous_config.get(config_key)
            current_value = current_config.get(config_key)

            previous_canonical = canonical_value(previous_value)
            current_canonical = canonical_value(current_value)

            if previous_canonical == current_canonical:
                continue

            known_values = seen_values[current_server_id][category_name]

            event_type = (
                "reverted"
                if current_canonical in known_values
                else "changed"
            )

            events.append({
                "id": f"{fingerprint.id}-{category_name}",
                "fingerprint_id": fingerprint.id,
                "server_id": current_server_id,
                "server_name": server_name,
                "category": category_name,
                "previous_value": previous_value,
                "new_value": current_value,
                "event_type": event_type,
                "detected_at": fingerprint.collected_at,
            })

            known_values.add(current_canonical)

        previous_configs[current_server_id] = current_config

    events.sort(
        key=lambda event: (
            event["detected_at"],
            event["fingerprint_id"]
        ),
        reverse=True
    )

    return events


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


class SettingsBody(BaseModel):
    poll_interval_seconds: int = Field(
        default=30,
        ge=10,
        le=3600,
        description="Polling interval between 10 and 3600 seconds"
    )

    theme: str = Field(
        default="light",
        pattern="^(light|dark)$"
    )


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
# SETTINGS ENDPOINTS
# --------------------------------------------------

@app.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    """Retrieve saved Configo application settings."""

    poll_setting = db.get(
        AppSetting,
        "poll_interval_seconds"
    )

    theme_setting = db.get(
        AppSetting,
        "theme"
    )

    return {
        "poll_interval_seconds": (
            poll_setting.value if poll_setting else 30
        ),
        "theme": (
            theme_setting.value if theme_setting else "light"
        ),
    }


@app.put("/settings")
def update_settings(
    body: SettingsBody,
    db: Session = Depends(get_db),
):
    """Save Configo application settings in SQLite."""

    settings_to_save = {
        "poll_interval_seconds": body.poll_interval_seconds,
        "theme": body.theme,
    }

    for key, value in settings_to_save.items():
        setting = db.get(AppSetting, key)

        if setting is None:
            setting = AppSetting(
                key=key,
                value=value
            )
            db.add(setting)
        else:
            setting.value = value

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to save application settings."
        )

    return {
        "message": "Settings saved successfully",
        "poll_interval_seconds": body.poll_interval_seconds,
        "theme": body.theme,
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
# DRIFT HISTORY ENDPOINT
# --------------------------------------------------

@app.get("/history")
def get_drift_history(
    server_id: int | None = Query(default=None, ge=1),
    category: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db)
):
    if category is not None and category not in BASELINE_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid category. Available categories: "
                + ", ".join(BASELINE_CATEGORIES.keys())
            )
        )

    if server_id is not None:
        server = db.query(Server).filter(
            Server.id == server_id
        ).first()

        if server is None:
            raise HTTPException(
                status_code=404,
                detail="Server not found"
            )

    events = build_history_events(
        db=db,
        server_id=server_id,
        category=category
    )

    total_events = len(events)
    paginated_events = events[offset:offset + limit]

    return {
        "total_events": total_events,
        "limit": limit,
        "offset": offset,
        "events": paginated_events,
    }


# --------------------------------------------------
# APPROVED BASELINE ENDPOINTS
# --------------------------------------------------

@app.get("/baseline")
def get_baseline(db: Session = Depends(get_db)):
    baseline = db.get(Baseline, 1)

    return baseline_to_dict(baseline)


@app.post("/baseline/capture")
def capture_baseline(
    body: BaselineBody,
    db: Session = Depends(get_db)
):
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
    Reset simulated fleet servers without changing the approved baseline.
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
