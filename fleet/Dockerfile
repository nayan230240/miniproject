# Image for one simulated fleet server (FastAPI).
# docker-compose builds this once and starts 5 containers from it.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Inside the container the fake server always listens on 8000.
# docker-compose maps 8001-8005 on your machine to this port.
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
