# Database tables for Configo.
# Think of these as spreadsheets stored in SQLite:
#   servers       = one row per simulated fleet machine
#   fingerprints  = one row per poll (every ~30 seconds)

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Server(Base):
    """A fleet machine we poll, for example fleet-1 at http://fleet-1:8000."""

    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Human-readable name, taken from the URL host (fleet-1, fleet-2, ...).
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Base URL we call, without the /config path.
    base_url: Mapped[str] = mapped_column(String(255))
    # Last time we successfully fetched /config.
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # One server has many fingerprints over time.
    fingerprints: Mapped[list["Fingerprint"]] = relationship(
        back_populates="server",
        cascade="all, delete-orphan",
    )


class Fingerprint(Base):
    """
    A snapshot of a server's config, stored as hashes.

    Why hashes? They are short, comparable, and do not need a full diff
    to answer "did this category change since last time?"
    """

    __tablename__ = "fingerprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"), index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    # SHA-256 of the entire normalized config JSON.
    full_hash: Mapped[str] = mapped_column(String(64))
    # SHA-256 of each category, so we can see *what* drifted later.
    os_version_hash: Mapped[str] = mapped_column(String(64))
    kernel_version_hash: Mapped[str] = mapped_column(String(64))
    packages_hash: Mapped[str] = mapped_column(String(64))
    ports_hash: Mapped[str] = mapped_column(String(64))
    env_vars_hash: Mapped[str] = mapped_column(String(64))
    ssh_hash: Mapped[str] = mapped_column(String(64))
    # Canonical JSON that was hashed (handy when you inspect the database).
    normalized_config: Mapped[str] = mapped_column(Text)

    server: Mapped["Server"] = relationship(back_populates="fingerprints")
