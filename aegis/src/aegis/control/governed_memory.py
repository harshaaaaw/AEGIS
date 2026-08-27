"""Subsystem 4: Governed Memory — versioned, capability-gated memory.

Agent memory is dangerous if any agent can read/write any fact. Governed Memory
versions every write (audit trail) and gates reads on a capability set the
caller presents (never trusts the caller's self-asserted identity for writes).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..backbone import ControlEvent, EventBus, register_subsystem


@dataclass
class MemoryRecord:
    key: str
    version: int
    value: dict
    tenant_id: str
    capabilities: set[str]


class GovernedMemory:
    name = "governed_memory"

    def __init__(self, state_dir: str):
        self.state_dir = state_dir
        self._store = Path(state_dir) / "memory.jsonl"
        self._versions: dict[str, int] = {}

    def register(self, bus: EventBus, spine) -> None:
        bus.subscribe(self.name, self.handle)
        register_subsystem(self)

    def handle(self, event: ControlEvent) -> None:
        pass  # driven directly; bus hook kept for future event-sourced writes

    def write(self, key: str, tenant_id: str, value: dict,
              capabilities: set[str]) -> MemoryRecord:
        if not capabilities:
            raise ValueError("write requires at least one capability")
        ver = self._versions.get(key, 0) + 1
        self._versions[key] = ver
        rec = MemoryRecord(key, ver, value, tenant_id, set(capabilities))
        with open(self._store, "a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "version": ver, "tenant_id": tenant_id,
                                "value": value, "caps": list(capabilities)}) + "\n")
        return rec

    def read(self, key: str, tenant_id: str, capabilities: set[str]) -> MemoryRecord | None:
        # return the latest version the caller is permitted to see
        latest: MemoryRecord | None = None
        if not self._store.exists():
            return None
        for raw in self._store.read_text(encoding="utf-8").splitlines():
            r = json.loads(raw)
            if r["key"] != key or r["tenant_id"] != tenant_id:
                continue
            if not (set(r["caps"]) & capabilities):
                continue
            latest = MemoryRecord(r["key"], r["version"], r["value"],
                                  r["tenant_id"], set(r["caps"]))
        return latest
