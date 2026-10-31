# Simulated fleet server.
# Config starts from docker-compose environment variables, then lives in
# memory so the demo can change it *without* restarting the container.

import copy
import os

from fastapi import FastAPI

app = FastAPI(
    title="Configo simulated server",
    description="Fake host that exposes GET /config for drift experiments.",
    version="0.0.1",
)


def env(name: str, default: str = "") -> str:
    """Read one environment variable, or use a default if it is missing."""
    return os.getenv(name, default)


def parse_packages(raw: str) -> dict:
    """Turn 'nginx=1.18.0,openssl=3.0.2' into {"nginx": "1.18.0", ...}."""
    packages = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        name, _, version = item.partition("=")
        packages[name.strip()] = version.strip()
    return packages


def parse_ports(raw: str) -> list:
    """Turn '22,80,443' into [22, 80, 443]."""
    ports = []
    for item in raw.split(","):
        item = item.strip()
        if item:
            ports.append(int(item))
    return ports


def parse_key_values(raw: str) -> dict:
    """Turn 'PermitRootLogin=no,Port=22' into a dict."""
    pairs = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        key, _, value = item.partition("=")
        pairs[key.strip()] = value.strip()
    return pairs


def config_from_env() -> dict:
    """Snapshot of whatever docker-compose baked into this container."""
    return {
        "os_version": env("OS_VERSION", "Ubuntu 22.04.5 LTS"),
        "kernel_version": env("KERNEL_VERSION", "5.15.0-119-generic"),
        "installed_packages": parse_packages(
            env("INSTALLED_PACKAGES", "nginx=1.18.0,openssl=3.0.2,python3=3.10.12,curl=7.81.0")
        ),
        "open_ports": parse_ports(env("OPEN_PORTS", "22,80,443")),
        "environment_variables": parse_key_values(
            env("SIMULATED_ENV_VARS", "APP_ENV=production,LOG_LEVEL=info,TZ=UTC")
        ),
        "ssh_settings": parse_key_values(
            env("SSH_SETTINGS", "PermitRootLogin=no,PasswordAuthentication=no,Port=22")
        ),
    }


# Live config. POST /apply-config and POST /simulate-drift edit this dict.
STATE = config_from_env()


@app.get("/health")
def health():
    """Tiny liveness check so you can see the fake server is up."""
    return {"status": "ok", "service": env("FLEET_NAME", "fleet-unknown")}


@app.get("/config")
def get_config():
    """Return this simulated machine's *current* configuration."""
    return STATE


@app.post("/apply-config")
def apply_config(payload: dict):
    """
    Replace the in-memory config (used by the demo 'reset to golden' flow).
    Expected keys match GET /config.
    """
    global STATE
    STATE = copy.deepcopy(payload)
    return {"ok": True, "config": STATE}


@app.post("/simulate-drift")
def simulate_drift():
    """
    Judge-visible live change:
      - open an extra high port (31337)
      - turn on SSH root login
    The next Configo poll will hash this and flag the host as drifted.
    """
    ports = list(STATE.get("open_ports") or [])
    if 31337 not in ports:
        ports.append(31337)
    STATE["open_ports"] = ports
    ssh = dict(STATE.get("ssh_settings") or {})
    ssh["PermitRootLogin"] = "yes"
    STATE["ssh_settings"] = ssh
    return {
        "ok": True,
        "changes": ["open_ports added 31337", "ssh_settings.PermitRootLogin=yes"],
        "config": STATE,
    }
