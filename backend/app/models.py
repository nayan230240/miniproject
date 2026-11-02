
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    base_url = Column(String, nullable=False)

    last_seen_at = Column(DateTime, nullable=True)

    fingerprints = relationship(
        "Fingerprint",
        back_populates="server",
        cascade="all, delete-orphan",
        order_by="Fingerprint.collected_at.desc()",
    )


class Fingerprint(Base):
    __tablename__ = "fingerprints"

    id = Column(Integer, primary_key=True, index=True)

    server_id = Column(
        Integer,
        ForeignKey("servers.id"),
        nullable=False,
        index=True,
    )

    collected_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    full_hash = Column(String, nullable=False)

    os_version_hash = Column(String, nullable=False)
    kernel_version_hash = Column(String, nullable=False)
    packages_hash = Column(String, nullable=False)
    ports_hash = Column(String, nullable=False)
    env_vars_hash = Column(String, nullable=False)
    ssh_hash = Column(String, nullable=False)

    normalized_config = Column(JSON, nullable=False)

    server = relationship(
        "Server",
        back_populates="fingerprints",
    )


class Baseline(Base):
    """
    Stores Configo's original engineer-approved configuration.

    The baseline is independent of the current fleet majority.
    It must only change when an engineer intentionally approves
    a new baseline.
    """

    __tablename__ = "baselines"

    # Configo uses one active baseline, with ID = 1.
    id = Column(Integer, primary_key=True, default=1)

    normalized_config = Column(JSON, nullable=False)

    category_hashes = Column(JSON, nullable=False)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    notes = Column(String, nullable=True)
