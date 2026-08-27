"""agent-sentinel: per-turn shield for LLM agents."""

from .audit import AuditLog
from .breaker import BreakerConfig, CircuitBreaker
from .firewall import Sentinel, LatencyBudgetExceeded
from .models import (
    Action, Channel, Decision, Finding, Label, ScanReport,
    Severity, ToolCall, ToolResult, TurnContext,
)

__version__ = "2.0.0"

__all__ = [
    "Action", "AuditLog", "BreakerConfig", "Channel", "CircuitBreaker",
    "Decision", "Finding", "Label", "LatencyBudgetExceeded", "ScanReport",
    "Sentinel", "Severity", "ToolCall", "ToolResult", "TurnContext",
]
