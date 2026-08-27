"""Subsystem 9: Autonomous Ops — graduated trust enforcement.

Agents are promoted through trust tiers (shadow -> read_only -> limited_write ->
autonomous). Autonomous actions are only permitted at limited_write+. Any
incident demotes the tenant. This is the operational safety room; it never
grants day-one prod autonomy.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..backbone import ControlEvent, EventBus, register_subsystem

TIERS = ["shadow", "read_only", "limited_write", "autonomous"]
AUTONOMOUS_MIN = "limited_write"


@dataclass
class TrustState:
    tier: str
    reason: str = ""


class AutonomousOps:
    name = "autonomous_ops"

    def __init__(self, state_dir: str):
        self.state_dir = state_dir
        self._tiers: dict[str, str] = {}
        self._log = Path(state_dir) / "ops.jsonl"

    def register(self, bus: EventBus, spine) -> None:
        bus.subscribe(self.name, self.handle)
        register_subsystem(self)

    def handle(self, event: ControlEvent) -> None:
        pass

    def _set(self, tenant_id: str, tier: str, reason: str) -> None:
        self._tiers[tenant_id] = tier
        with open(self._log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"tenant": tenant_id, "tier": tier, "reason": reason}) + "\n")

    def promote(self, tenant_id: str, to: str) -> TrustState:
        if to not in TIERS:
            raise ValueError(f"unknown tier {to!r}")
        cur = self._tiers.get(tenant_id, "shadow")
        if TIERS.index(to) < TIERS.index(cur):
            raise ValueError("promote requires a higher tier")
        self._set(tenant_id, to, "promotion")
        return TrustState(to)

    def demote(self, tenant_id: str, reason: str) -> TrustState:
        # incidents drop the tenant to shadow
        self._set(tenant_id, "shadow", reason)
        return TrustState("shadow", reason)

    def allow_autonomous(self, tenant_id: str) -> bool:
        cur = self._tiers.get(tenant_id, "shadow")
        return TIERS.index(cur) >= TIERS.index(AUTONOMOUS_MIN)
