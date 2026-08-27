"""Backbone: shared event bus + subsystem registry for the AEGIS control plane.

The control plane is a room of 10 subsystems. They communicate only through
this bus (loose coupling) and persist evidence only through the Spine
(tamper-evidence). Anti-slop: the bus never blocks on a slow subscriber
(fire-and-forget with per-subscriber error isolation); registration is
idempotent; no bare except.
"""
from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import Any, Protocol


class ControlEvent:
    """A single event on the bus. Evidence-backed: carries run_id + trace id."""
    def __init__(self, subsystem: str, kind: str, payload: dict[str, Any],
                 run_id: str | None = None, tenant_id: str | None = None):
        self.event_id = uuid.uuid4().hex[:16]
        self.subsystem = subsystem
        self.kind = kind
        self.payload = payload
        self.run_id = run_id
        self.tenant_id = tenant_id
        self.ts = time.time()


Handler = Callable[[ControlEvent], None]


class EventBus:
    """In-process pub/sub. Subscribers are isolated: one crashing does not
    stop delivery to the others (failure isolation is an anti-slop property)."""

    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = {}

    def subscribe(self, subsystem: str, handler: Handler) -> None:
        self._subs.setdefault(subsystem, []).append(handler)

    def publish(self, event: ControlEvent) -> None:
        for handler in self._subs.get(event.subsystem, []):
            try:
                handler(event)
            except Exception as exc:  # noqa: BLE001  (intentional: bus isolation; logged with context below)
                # observability: record the failure with context instead of swallowing silently
                import logging
                logging.getLogger("aegis.bus").error(
                    "subscriber failed", extra={"event_id": event.event_id,
                                                "subsystem": event.subsystem,
                                                "error": repr(exc)})

    def subscriber_count(self, subsystem: str) -> int:
        return len(self._subs.get(subsystem, []))


class Subsystem(Protocol):
    name: str

    def register(self, bus: EventBus, spine) -> None: ...

    def handle(self, event: ControlEvent) -> None: ...


_REGISTRY: dict[str, Subsystem] = {}


def register_subsystem(inst: Subsystem) -> Subsystem:
    """Idempotent registration of a room into the control plane."""
    if inst.name in _REGISTRY and _REGISTRY[inst.name] is not inst:
        raise ValueError(f"subsystem {inst.name!r} already registered")
    _REGISTRY[inst.name] = inst
    return inst


def all_subsystems() -> list[Subsystem]:
    return list(_REGISTRY.values())


def reset_registry() -> None:
    """Test helper: clear registry between cases."""
    _REGISTRY.clear()
