"""Consumer test: ControlPlane.boot wires all 10 subsystems onto the bus (plane.py 73%)."""
from __future__ import annotations

from aegis.backbone import EventBus, reset_registry
from aegis.control.plane import ControlPlane


def test_control_plane_boots_all_subsystems():
    reset_registry()
    bus = EventBus()
    from aegis.spine import Spine, SpineConfig
    spine = Spine(SpineConfig(db_path=":memory:", jwt_secret="0" * 32))
    plane = ControlPlane(spine, state_dir="")
    plane.boot(bus)
    assert len(plane.subsystems) == 10
    names = {s.name for s in plane.subsystems}
    expected = {"swapwatch", "roi_attest", "governed_memory", "contract_intel",
                "twin_truth", "causal_decisions", "sim_rl_factory",
                "autonomous_ops", "panes", "ship_gate"}
    assert expected <= names
    gate_room = plane.get("ship_gate")
    assert gate_room is not None
    reset_registry()
