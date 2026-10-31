# Configo / DriftWise

Configuration drift is silent: one host gets an older package, an extra open port, or a weaker SSH setting, and the rest of the fleet does not. Configo watches a small simulated fleet, fingerprints each machine, and flags the odd ones out.

## Approach

1. **Five fake servers** (`fleet/`) each expose `GET /config`. Three start identical; two can be different. Config is held in memory so a demo can change it live.
2. **The backend** polls every 30 seconds, stores a SHA-256 fingerprint per category (packages, ports, SSH, …) in SQLite, and clusters hosts with scikit-learn DBSCAN. The largest cluster is the majority; everyone else is drift.
3. **An LLM** (optional) turns the diff into plain language: what changed, why it matters, what to do next. If `LLM_API_KEY` is missing, a fallback summary is returned.
4. **DriftWise** is the dashboard: counts, status badges, diffs, and the explanation. **Simulate drift** pokes a healthy host immediately (does not wait for the 30s poll). **Reset demo** puts every host back on the golden baseline.

## Run it

```bash
docker compose up --build
```

- UI: http://localhost:5173
- API: http://localhost:8000/docs
- Optional: `LLM_API_KEY` (or `OPENAI_API_KEY`) in the environment for live explanations

## Demo flow (about one minute)

1. Open DriftWise. Click **Reset demo** so all five hosts are healthy (5 / 5 / 0).
2. Click **Simulate drift**. A healthy host opens port `31337` and sets `PermitRootLogin=yes`.
3. The poller runs at once: that host turns violet, **Drifted** goes to 1, and the detail panel shows the category diff.
4. Read **AI explanation** (LLM if a key is set, otherwise the built-in fallback).
