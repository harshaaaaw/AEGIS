"""Core types for agent-sentinel v2: per-turn security labeling."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Channel(str, Enum):
    USER_INPUT = "user_input"      # trusted instruction space
    TOOL_RESULT = "tool_result"    # attacker-influenceable
    OUTBOUND = "outbound"          # leaving the perimeter


class Severity(int, Enum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class Action(str, Enum):
    ALLOW = "ALLOW"
    REDACT = "REDACT"
    BLOCK = "BLOCK"


class Label(str, Enum):
    """Per-turn semantic labels. These are the stable event names you can
    pipe into an eval set, a fine-tune dataset, or an RL reward term."""

    OK = "turn_ok"
    INJECTION_ATTEMPT = "injection_attempt"
    SECRET_EXPOSURE = "secret_exposure"
    EXFIL_ATTEMPT = "exfil_attempt"
    POLICY_VIOLATION = "policy_violation"
    CONTENT_REDACTED = "content_redacted"
    CONTENT_BLOCKED = "content_blocked"
    BREAKER_TRIPPED = "breaker_tripped"
    LATENCY_BUDGET_BREACH = "latency_budget_breach"


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: Severity
    span: tuple[int, int]
    excerpt: str
    detail: str


@dataclass(frozen=True)
class TurnContext:
    """Identity attached at the root of a request; children inherit it."""
    tenant_id: str = "default"
    session_id: str = ""
    turn_id: str = ""

    @staticmethod
    def new(tenant_id: str = "default", session_id: str | None = None) -> "TurnContext":
        return TurnContext(
            tenant_id=tenant_id,
            session_id=session_id or uuid.uuid4().hex[:12],
            turn_id=uuid.uuid4().hex[:12],
        )


@dataclass
class ScanReport:
    channel: Channel
    text_len: int
    findings: list[Finding] = field(default_factory=list)
    elapsed_us: float = 0.0

    @property
    def max_severity(self) -> Severity:
        return max((f.severity for f in self.findings), default=Severity.NONE)


@dataclass(frozen=True)
class Decision:
    action: Action
    labels: tuple[Label, ...]
    reasons: tuple[str, ...]
    text_out: str | None          # redacted/stubbed text when not ALLOW
    report: ScanReport
    ctx: TurnContext


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    call: ToolCall
    text: str
    ok: bool = True


def now_us() -> float:
    return time.perf_counter_ns() / 1000.0
