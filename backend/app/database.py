# SQLite + SQLAlchemy setup (placeholder).
# Nothing is stored yet — this just prepares the connection for later features.

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Local default: a file named configo.db in the backend folder.
# Docker overrides this so the file lives on a volume under /app/data.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./configo.db")

# check_same_thread=False is required for SQLite when FastAPI uses multiple threads.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


class Base(DeclarativeBase):
    """Parent class for future database tables (models)."""

    pass


# SessionLocal() creates one database session (a short-lived conversation with SQLite).
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency placeholder. Routes can use this later."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
