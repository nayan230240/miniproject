# Placeholder "fleet agent".
# Later this process will collect a machine's config and send it to Configo.
# Right now it only prints a heartbeat so the container stays running.

import os
import time

# docker-compose sets FLEET_NAME to fleet-1, fleet-2, ...
name = os.getenv("FLEET_NAME", "unknown-host")

print(f"[configo-fleet] {name} started (placeholder only, no drift checks yet)")

while True:
    print(f"[configo-fleet] {name} heartbeat")
    time.sleep(30)
