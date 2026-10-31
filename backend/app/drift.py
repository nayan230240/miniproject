# Drift detector.
#
# Algorithm (plain English):
#   1. Take the newest fingerprint for every server.
#   2. Compare servers by their *category hashes* (packages, ports, ssh, ...).
#      Distance = how many categories differ (0 = identical config).
#   3. Run DBSCAN from scikit-learn on that distance matrix.
#      Servers with distance 0 are neighbors. A group of 2+ identical
#      servers becomes a cluster. Unique machines are labeled -1 (noise).
#   4. The largest cluster is the "majority" (the golden config).
#   5. Anyone not in that cluster is an outlier. For each outlier we
#      list the categories whose hashes differ from the majority.
#
# Why hashes instead of raw JSON?
#   Comparing six short strings is enough to know *which* section drifted.
#   We still attach the real JSON values so the API can show the difference.

from __future__ import annotations

import json
from collections import Counter

import numpy as np
from sklearn.cluster import DBSCAN
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fingerprint, Server

# Names shown in GET /drift, paired with the Fingerprint columns we compare.
CATEGORIES = [
    ("os_version", "os_version_hash"),
    ("kernel_version", "kernel_version_hash"),
    ("installed_packages", "packages_hash"),
    ("open_ports", "ports_hash"),
    ("environment_variables", "env_vars_hash"),
    ("ssh_settings", "ssh_hash"),
]


def latest_fingerprint(db: Session, server_id: int) -> Fingerprint | None:
    return db.scalar(
        select(Fingerprint)
        .where(Fingerprint.server_id == server_id)
        .order_by(Fingerprint.collected_at.desc(), Fingerprint.id.desc())
    )


def snapshots(db: Session) -> list[tuple[Server, Fingerprint]]:
    """One (server, newest fingerprint) pair per machine we have seen."""
    servers = db.scalars(select(Server).order_by(Server.id)).all()
    rows = []
    for server in servers:
        fp = latest_fingerprint(db, server.id)
        if fp is not None:
            rows.append((server, fp))
    return rows


def category_hashes(fp: Fingerprint) -> list[str]:
    return [getattr(fp, column) for _, column in CATEGORIES]


def hamming_distance_matrix(hash_rows: list[list[str]]) -> np.ndarray:
    """
    Distance[i][j] = number of categories that differ between server i and j.
    Example: same everything except openssl -> distance 1.
    """
    n = len(hash_rows)
    matrix = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(i + 1, n):
            dist = sum(a != b for a, b in zip(hash_rows[i], hash_rows[j]))
            matrix[i, j] = matrix[j, i] = dist
    return matrix


def cluster_labels(hash_rows: list[list[str]]) -> list[int]:
    """
    DBSCAN settings:
      metric='precomputed'  -> we pass our Hamming matrix
      eps=0.5               -> only distance 0 (perfect match) counts as neighbors
      min_samples=2         -> a cluster needs at least two identical servers
    Isolated machines (the drifted ones in this demo) get label -1.
    """
    if len(hash_rows) == 0:
        return []
    if len(hash_rows) == 1:
        return [0]
    matrix = hamming_distance_matrix(hash_rows)
    model = DBSCAN(eps=0.5, min_samples=2, metric="precomputed")
    return [int(label) for label in model.fit_predict(matrix)]


def majority_cluster_id(labels: list[int]) -> int | None:
    """Largest non-noise cluster. None if nobody clustered (all unique)."""
    counted = Counter(label for label in labels if label != -1)
    if not counted:
        return None
    # Tie-break: bigger count, then smaller cluster id.
    return sorted(counted, key=lambda label: (-counted[label], label))[0]


def config_value(fp: Fingerprint, category: str):
    """Read one category out of the stored normalized JSON."""
    try:
        payload = json.loads(fp.normalized_config)
    except (TypeError, json.JSONDecodeError):
        return None
    return payload.get(category)


def detect_drift(db: Session) -> dict:
    """Build the GET /drift payload from the latest fingerprints."""
    rows = snapshots(db)
    labels = cluster_labels([category_hashes(fp) for _, fp in rows])
    majority_id = majority_cluster_id(labels)

    clusters: dict[int, list[dict]] = {}
    for (server, fp), label in zip(rows, labels):
        clusters.setdefault(label, []).append(
            {"id": server.id, "name": server.name, "fingerprint_id": fp.id}
        )

    majority_members = [
        (server, fp)
        for (server, fp), label in zip(rows, labels)
        if majority_id is not None and label == majority_id
    ]
    # Baseline = first majority server (they all share the same category hashes).
    baseline = majority_members[0][1] if majority_members else None

    outliers = []
    for (server, fp), label in zip(rows, labels):
        if majority_id is not None and label == majority_id:
            continue
        if baseline is None:
            # No majority at all (every host unique). Compare to nothing useful.
            continue
        differing = []
        for category, column in CATEGORIES:
            if getattr(fp, column) != getattr(baseline, column):
                differing.append(
                    {
                        "category": category,
                        "majority_value": config_value(baseline, category),
                        "server_value": config_value(fp, category),
                    }
                )
        if not differing:
            continue
        outliers.append(
            {
                "server_id": server.id,
                "name": server.name,
                "cluster_id": label,
                "fingerprint_id": fp.id,
                "full_hash": fp.full_hash,
                "collected_at": fp.collected_at.isoformat() if fp.collected_at else None,
                "differing_categories": differing,
            }
        )

    return {
        "algorithm": "DBSCAN on Hamming distance of category hashes",
        "explanation": (
            "Each server is six hashes (os, kernel, packages, ports, env, ssh). "
            "Distance is how many of those hashes differ. DBSCAN groups servers "
            "that match on every category. The biggest group is the majority. "
            "Everyone else is an outlier, with the exact categories that drifted."
        ),
        "parameters": {"eps": 0.5, "min_samples": 2, "metric": "precomputed"},
        "majority": {
            "cluster_id": majority_id,
            "server_count": len(majority_members),
            "servers": [
                {"id": server.id, "name": server.name} for server, _ in majority_members
            ],
        },
        "clusters": [
            {"cluster_id": cluster_id, "servers": members}
            for cluster_id, members in sorted(clusters.items(), key=lambda item: item[0])
        ],
        "outliers": outliers,
    }
