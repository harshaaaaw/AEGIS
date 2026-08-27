"""Subsystem 5: Contract & Spend Intel — authorized-tool / budget enforcement.

Before an agent calls a tool, this room checks the call against the agent's
authorized tool set (a contract). Unauthorized calls (scope creep, e.g. DROP
TABLE) are blocked. Spend is tallied so budget overruns are detectable.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..backbone import ControlEvent, EventBus, register_subsystem


@dataclass
class CallVerdict:
    allowed: bool
    reason: str


class ContractIntel:
    name = "contract_intel"

    def __init__(self, state_dir: str):
        self.state_dir = state_dir
        self._contracts: dict[str, set[str]] = {}
        self._spend: dict[str, float] = {}

    def register(self, bus: EventBus, spine) -> None:
        bus.subscribe(self.name, self.handle)
        register_subsystem(self)

    def handle(self, event: ControlEvent) -> None:
        if event.kind == "tool_call":
            self.check_call(event.payload.get("agent", "?"),
                            event.tenant_id or "?", event.payload.get("tool", "?"))

    def set_authorized(self, agent: str, tenant_id: str, tools: set[str]) -> None:
        self._contracts[f"{tenant_id}:{agent}"] = set(tools)

    def check_call(self, agent: str, tenant_id: str, tool: str) -> CallVerdict:
        allowed = tool in self._contracts.get(f"{tenant_id}:{agent}", set())
        return CallVerdict(
            allowed=allowed,
            reason=("ok" if allowed else f"tool {tool!r} not in authorized contract"))

    def record_spend(self, tenant_id: str, usd: float) -> None:
        self._spend[tenant_id] = self._spend.get(tenant_id, 0.0) + usd

    def spend(self, tenant_id: str) -> float:
        return self._spend.get(tenant_id, 0.0)
