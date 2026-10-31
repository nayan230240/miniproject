# Tiny image for one simulated fleet machine.
FROM python:3.12-slim

WORKDIR /app
COPY simulate.py .

# This process just stays alive and prints a heartbeat.
CMD ["python", "-u", "simulate.py"]
