
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.models import Baseline, Fingerprint, Server


# --------------------------------------------------
# CONFIGURATION CATEGORIES
# --------------------------------------------------

CATEGORIES = {
    "os_version": "os_version",
    "kernel_version": "kernel_version",
    "installed_packages": "installed_packages",
    "open_ports": "open_ports",
    "environment_variables": "environment_variables",
    "ssh_settings": "ssh_settings",
}


# --------------------------------------------------
# CONFIGURATION NORMALIZATION
# --------------------------------------------------

def normalize_config(config: Any) -> dict:
    """
    Convert stored JSON strings or dictionaries into
    a consistent Python dictionary.
    """

    if config is None:
        return {}

    # Handle JSON strings, including double-encoded JSON.
    while isinstance(config, str):
        try:
            config = json.loads(config)
        except (json.JSONDecodeError, TypeError):
            return {}

    if isinstance(config, dict):
        return config

    return {}


def canonical_config(config: dict) -> str:
    """Create a stable representation for comparison."""

    return json.dumps(
        config,
        sort_keys=True,
        separators=(",", ":"),
        default=str
    )


# --------------------------------------------------
# FETCH LATEST SERVER SNAPSHOTS
# --------------------------------------------------

def snapshots(db: Session) -> list[dict]:
    """
    Get the latest fingerprint for every registered server.
    """

    servers = db.query(Server).order_by(Server.id).all()

    result = []

    for server in servers:
        latest = (
            db.query(Fingerprint)
            .filter(Fingerprint.server_id == server.id)
            .order_by(Fingerprint.collected_at.desc())
            .first()
        )

        if latest is None:
            continue

        config = normalize_config(latest.normalized_config)

        result.append({
            "id": server.id,
            "name": server.name,
            "server": server,
            "fingerprint": latest,
            "config": config,
        })

    return result


# --------------------------------------------------
# CATEGORY COMPARISON
# --------------------------------------------------

def differing_categories(
    reference_config: Any,
    comparison_config: Any
) -> list[dict]:

    reference_config = normalize_config(reference_config)
    comparison_config = normalize_config(comparison_config)

    differences = []

    for category, config_key in CATEGORIES.items():

        reference_value = reference_config.get(config_key)
        comparison_value = comparison_config.get(config_key)

        if canonical_config({"value": reference_value}) != canonical_config(
            {"value": comparison_value}
        ):
            differences.append({
                "category": category,
                "majority_value": reference_value,
                "server_value": comparison_value,
            })

    return differences


def compare_with_baseline(
    current_config: Any,
    baseline_config: Any
) -> list[dict]:

    current_config = normalize_config(current_config)
    baseline_config = normalize_config(baseline_config)

    differences = []

    for category, config_key in CATEGORIES.items():

        baseline_value = baseline_config.get(config_key)
        current_value = current_config.get(config_key)

        if canonical_config({"value": baseline_value}) != canonical_config(
            {"value": current_value}
        ):
            differences.append({
                "category": category,
                "baseline_value": baseline_value,
                "current_value": current_value,
            })

    return differences


# --------------------------------------------------
# BUILD MAJORITY CONFIGURATION
# --------------------------------------------------

def build_majority(snapshot_list: list[dict]) -> dict:

    groups = defaultdict(list)

    for item in snapshot_list:
        config = normalize_config(item["config"])
        groups[canonical_config(config)].append(item)

    if not groups:
        return {
            "servers": [],
            "config": {},
            "count": 0,
            "total_servers": 0,
            "percentage": 0,
            "has_majority": False,
        }

    majority_key = max(
        groups,
        key=lambda key: len(groups[key])
    )

    majority_group = groups[majority_key]

    total = len(snapshot_list)
    count = len(majority_group)

    return {
        "servers": [
            {
                "id": item["id"],
                "name": item["name"],
            }
            for item in majority_group
        ],
        "config": normalize_config(majority_group[0]["config"]),
        "count": count,
        "total_servers": total,
        "percentage": round((count / total) * 100, 2),
        "has_majority": count > total / 2,
    }


# --------------------------------------------------
# MAIN DRIFT DETECTION
# --------------------------------------------------

def detect_drift(db: Session) -> dict:

    snapshot_list = snapshots(db)

    total_servers = len(snapshot_list)

    majority = build_majority(snapshot_list)

    majority_config = normalize_config(majority["config"])

    # Fetch the approved original baseline.
    baseline_record = db.get(Baseline, 1)

    baseline_config = (
        normalize_config(baseline_record.normalized_config)
        if baseline_record is not None
        else None
    )

    # --------------------------------------------------
    # COMPARE EVERY SERVER
    # --------------------------------------------------

    outliers = []
    server_comparisons = []

    for item in snapshot_list:

        server_config = normalize_config(item["config"])

        # First comparison: server against majority.
        peer_differences = differing_categories(
            majority_config,
            server_config
        )

        # Second comparison: server against approved baseline.
        baseline_differences = (
            compare_with_baseline(
                server_config,
                baseline_config
            )
            if baseline_config is not None
            else []
        )

        if baseline_config is None:
            baseline_status = "not_configured"
        elif baseline_differences:
            baseline_status = "deviates"
        else:
            baseline_status = "compliant"

        comparison = {
            "server_id": item["id"],
            "name": item["name"],
            "is_outlier": bool(peer_differences),
            "differing_categories": peer_differences,
            "baseline_differences": baseline_differences,
            "baseline_status": baseline_status,
        }

        server_comparisons.append(comparison)

        # Include servers with peer drift OR baseline deviations.
        if peer_differences or baseline_differences:
            outliers.append(comparison)

    # --------------------------------------------------
    # COMPARE MAJORITY AGAINST ORIGINAL BASELINE
    # --------------------------------------------------

    if baseline_config is None:
        majority_baseline_differences = []
        majority_baseline_status = "not_configured"

    else:
        majority_baseline_differences = compare_with_baseline(
            majority_config,
            baseline_config
        )

        majority_baseline_status = (
            "deviates"
            if majority_baseline_differences
            else "compliant"
        )

    # --------------------------------------------------
    # BUILD CONFIGURATION GROUPS
    # --------------------------------------------------

    clusters = []

    grouped = defaultdict(list)

    for item in snapshot_list:
        grouped[canonical_config(item["config"])].append(item)

    for group in grouped.values():
        clusters.append({
            "count": len(group),
            "servers": [
                {
                    "id": item["id"],
                    "name": item["name"],
                }
                for item in group
            ],
            "config": normalize_config(group[0]["config"]),
        })

    # --------------------------------------------------
    # BASELINE INFORMATION
    # --------------------------------------------------

    if baseline_record is None:
        baseline_info = {
            "configured": False,
            "config": None,
            "created_at": None,
            "updated_at": None,
            "notes": None,
        }

    else:
        baseline_info = {
            "configured": True,
            "config": baseline_config,
            "created_at": baseline_record.created_at,
            "updated_at": baseline_record.updated_at,
            "notes": baseline_record.notes,
        }

    # --------------------------------------------------
    # FINAL RESPONSE
    # --------------------------------------------------

    return {
        "total_servers": total_servers,

        "majority": majority,

        "clusters": clusters,

        "outliers": outliers,

        "server_comparisons": server_comparisons,

        "baseline": baseline_info,

        "majority_vs_baseline": {
            "status": majority_baseline_status,
            "differing_categories": majority_baseline_differences,
        },
    }
