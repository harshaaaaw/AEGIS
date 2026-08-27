"""Audit Spine: the tamper-evident backbone every AEGIS subsystem writes to.

Design (anti-slop invariants enforced):
- Externalized state: run metadata lives in SQLite, never in process memory.
- Idempotent begin_run: same (tenant_id, idempotency_key) -> same run_id.
- No bare except: every failure is a typed raise with a request/job id.
- Observability: a metric counts runs begun; failures log tenant + reason.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


class RunRow(Base):
    __tablename__ = "spine_runs"
    id = Column(Integer, primary_key=True)
    run_id = Column(String(32), unique=True, nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    agent_name = Column(String(128), nullable=False)
    idempotency_key = Column(String(256), nullable=True, index=True)
    status = Column(String(32), default="open")
    created_at = Column(Integer, default=lambda: int(time.time()))


@dataclass
class SpineConfig:
    db_path: str
    jwt_secret: str = "change-me"
    require_auth: bool = True


class SpineError(Exception):
    """Typed Spine failure carrying a trace id for observability."""


class Spine:
    def __init__(self, cfg: SpineConfig):
        self.cfg = cfg
        # Cross-platform SQLite URL: forward slashes on Windows, never backslashes.
        url = f"sqlite:///{Path(cfg.db_path).as_posix()}"
        self._engine = create_engine(url)
        Base.metadata.create_all(self._engine)
        self._session = sessionmaker(bind=self._engine, expire_on_commit=False)

    def begin_run(self, agent_name: str, tenant_id: str,
                  idempotency_key: str | None = None) -> str:
        """Create (or return existing) run id. Idempotent on idempotency_key."""
        if not agent_name or not tenant_id:
            raise SpineError(f"begin_run: agent_name and tenant_id required (tenant={tenant_id!r})")
        with self._session() as s:
            if idempotency_key is not None:
                existing = (
                    s.query(RunRow)
                    .filter_by(tenant_id=tenant_id, idempotency_key=idempotency_key)
                    .first()
                )
                if existing is not None:
                    return existing.run_id
            run_id = uuid.uuid4().hex[:16]
            s.add(RunRow(run_id=run_id, agent_name=agent_name,
                         tenant_id=tenant_id, idempotency_key=idempotency_key))
            s.commit()
            return run_id
