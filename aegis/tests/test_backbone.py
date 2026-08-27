"""Backbone tests: event bus isolation + subsystem registration."""
from __future__ import annotations

from aegis.backbone import ControlEvent, EventBus, register_subsystem, reset_registry


class _FakeSubsystem:
    name = "fake"

    def __init__(self) -> None:
        self.seen: list[ControlEvent] = []

    def register(self, bus, spine) -> None:
        bus.subscribe(self.name, self.handle)

    def handle(self, event: ControlEvent) -> None:
        self.seen.append(event)


def test_bus_delivers_to_subscriber():
    bus = EventBus()
    sub = _FakeSubsystem()
    sub.register(bus, None)
    bus.publish(ControlEvent("fake", "ping", {"x": 1}))
    assert len(sub.seen) == 1
    assert sub.seen[0].payload["x"] == 1


def test_bus_isolates_failing_subscriber():
    bus = EventBus()
    good = _FakeSubsystem()
    good.register(bus, None)

    def boom(event: ControlEvent) -> None:
        raise RuntimeError("subsystem on fire")

    bus.subscribe("fake", boom)
    # a crashing subscriber must not stop the good one from receiving
    bus.publish(ControlEvent("fake", "ping", {"x": 2}))
    assert len(good.seen) == 1


def test_registration_idempotent():
    reset_registry()
    sub = _FakeSubsystem()
    register_subsystem(sub)
    register_subsystem(sub)  # same instance -> no raise
    # a different instance with same name must raise
    class Other(_FakeSubsystem):
        pass
    other = Other()
    try:
        register_subsystem(other)
        assert False, "expected ValueError on duplicate name"
    except ValueError:
        pass
    reset_registry()
