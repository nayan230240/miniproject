# Small Python image for the Configo API.
FROM python:3.12-slim

# All app files live under /app inside the container.
WORKDIR /app

# Install Python packages first so Docker can cache this layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend source.
COPY . .

# Folder for the SQLite database file (see docker-compose volume).
RUN mkdir -p /app/data

# FastAPI is served by Uvicorn on port 8000.
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
