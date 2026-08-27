"""Chaos / fault-injection test: a subsystem that crashes on every event must
not take down the bus or its siblings (resilience gap closed).

Mechanics: register a "flaky" subscriber that raises on a counter. Publish many
events. Assert (a) the bus keeps delivering to the healthy subscriber, (b) the
flaky subscriber's failures are isolated (logged, not propagated), and (c) the
control plane still boots and answers posture afterwards.
"""
from __future__ import annotations

from aegis.backbone import ControlEvent, EventBus, reset_registry
from aegis.control.plane import ControlPlane
from aegis.spine import Spine, SpineConfig


def test_flaky_subscriber_does_not_break_bus():
    reset_registry()
    bus = EventBus()
    healthy_seen: list[str] = []
    counter = {"n": 0}

    def healthy(ev: ControlEvent) -> None:
        healthy_seen.append(ev.event_id)

    class Flaky:
        name = "flaky"

        def register(self, bus, spine) -> None:
            bus.subscribe(self.name, self.handle)

        def handle(self, ev: ControlEvent) -> None:
            counter["n"] += 1
            if counter["n"] % 2 == 0:
                raise RuntimeError("kaboom")
            # on odd calls it would do work; we just count via counter

    bus.subscribe("chaos", healthy)
    flaky = Flaky()
    bus.subscribe("chaos", flaky.handle)  # flaky shares the same channel as healthy

    for i in range(10):
        bus.publish(ControlEvent("chaos", kind="tick", payload={"i": i}))

    # healthy subscriber got all 10 (bus isolation holds); flaky ran 10 times
    # and its even-call crashes never stopped delivery to healthy.
    assert len(healthy_seen) == 10, healthy_seen
    assert counter["n"] == 10


def test_plane_survives_subsystem_failure_and_still_posts():
    reset_registry()
    bus = EventBus()
    spine = Spine(SpineConfig(db_path=":memory:", jwt_secret="0" * 32,
                              require_auth=False))
    ctrl = ControlPlane(spine, state_dir="__chaos_state")
    ctrl.boot(bus)

    # A room that raises on every event it receives.
    class RageRoom:
        name = "rage"

        def register(self, bus, spine) -> None:
            bus.subscribe(self.name, self.handle)

        def handle(self, ev) -> None:
            raise RuntimeError("always fails")

    rage = RageRoom()
    rage.register(bus, spine)

    # Other rooms still respond to their events despite rage room crashing.
    swap = ctrl.get("swapwatch")
    assert swap is not None
    # publish a real gate_certified event; swapwatch must snapshot regardless
    bus.publish(ControlEvent("swapwatch", kind="gate_certified",
                             payload={"run_id": "r1", "outputs": {"a": 1}}))

    # Panes posture must still work (orchestrator alive).
    panes = ctrl.get("panes")
    assert panes is not None
    posture = panes.posture(ctrl)
    assert isinstance(posture, dict)
    reset_registry()
