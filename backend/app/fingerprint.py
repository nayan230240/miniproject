# Fingerprint helpers.
# A fingerprint is a SHA-256 hash of a *normalized* config.
#
# Normalization matters because JSON like {"b":1,"a":2} and {"a":2,"b":1}
# means the same thing. We sort keys (and sort lists) so the hash is stable.

import hashlib
import json


def normalize(value):
    """
    Recursively make a value hash-friendly:
      - dicts: keys sorted
      - lists: each item normalized, then sorted when possible
      - everything else: left as-is (strings, numbers, bools, None)
    """
    if isinstance(value, dict):
        return {key: normalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        items = [normalize(item) for item in value]
        try:
            # Sort so [443, 22, 80] and [22, 80, 443] hash the same.
            return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
        except TypeError:
            return items
    return value


def canonical_json(value) -> str:
    """Turn a Python object into one exact JSON string (no extra spaces)."""
    return json.dumps(normalize(value), sort_keys=True, separators=(",", ":"))


def sha256_hex(text: str) -> str:
    """Return the SHA-256 hex digest of a string (always 64 characters)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fingerprint_config(config: dict) -> dict:
    """
    Build hashes for the whole config and for each category.

    Categories match the fleet /config payload:
      os_version, kernel_version, installed_packages,
      open_ports, environment_variables, ssh_settings
    """
    normalized = canonical_json(config)
    return {
        "full_hash": sha256_hex(normalized),
        "os_version_hash": sha256_hex(canonical_json(config.get("os_version"))),
        "kernel_version_hash": sha256_hex(canonical_json(config.get("kernel_version"))),
        "packages_hash": sha256_hex(canonical_json(config.get("installed_packages"))),
        "ports_hash": sha256_hex(canonical_json(config.get("open_ports"))),
        "env_vars_hash": sha256_hex(canonical_json(config.get("environment_variables"))),
        "ssh_hash": sha256_hex(canonical_json(config.get("ssh_settings"))),
        "normalized_config": normalized,
    }
