"""Core types for token-governor."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class SpendStatus(str, Enum):
    OK = "OK"            # inside budget
    SOFT = "SOFT"        # crossed soft threshold; alert fired, spend allowed
    HARD = "HARD"        # cap reached; spend must be refused/rerouted


@dataclass(frozen=True)
class TurnContext:
    tenant_id: str
    workflow: str
    session_id: str

    @staticmethod
    def new(tenant_id: str = "default", workflow: str = "default") -> TurnContext:
        return TurnContext(
            tenant_id=tenant_id,
            workflow=workflow,
            session_id=uuid.uuid4().hex[:12],
        )


@dataclass
class CallRecord:
    """One billable model call."""
    ctx: TurnContext
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    ts: float = field(default_factory=time.time)


@dataclass
class Outcome:
    """A unit of requested work; may contain many calls (retries, tools)."""
    session_id: str
    ctx: TurnContext
    success: bool | None = None      # None while open
    call_cost_usd: float = 0.0
    calls: int = 0


class PricingError(KeyError):
    pass


def now() -> float:
    return time.time()


def today_key(ts: float | None = None) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts if ts is not None else now()))
