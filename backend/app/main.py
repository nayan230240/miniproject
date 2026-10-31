# Configo API entry point.
# Run locally: uvicorn app.main:app --reload
# Open docs later at: http://localhost:8000/docs

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine

app = FastAPI(
    title="Configo",
    description="AI-powered configuration drift detector (scaffold only).",
    version="0.0.1",
)

# The React app runs on another port, so we allow browser requests from anywhere for now.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    # Creates SQLite tables when we add models later. Harmless with an empty Base.
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    """Simple liveness check used by Docker and by you in the browser."""
    return {"status": "ok", "service": "configo-backend"}
