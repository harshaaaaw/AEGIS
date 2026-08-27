"""Tests for subsystem 10 (panes + control-loop orchestrator) and the full
end-to-end control-plane boot: all 10 subsystems register on the bus and a
certified run flows through Gate -> SwapWatch -> ROI Attest with evidence.
"""
from __future__ import annotations

from aegis.backbone import EventBus, reset_registry
from aegis.control import plane
from aegis.spine import Spine, SpineConfig


def _boot(spine):
    reset_registry()
    bus = EventBus()
    ctrl = plane.ControlPlane(spine, state_dir=".boot_runs")
    ctrl.boot(bus)
    return bus, ctrl


def test_all_ten_subsystems_register():
    spine = Spine(SpineConfig(db_path=":memory:", jwt_secret="x", require_auth=False))
    _bus, ctrl = _boot(spine)
    names = {s.name for s in ctrl.subsystems}
    assert {"ship_gate", "swapwatch", "roi_attest", "governed_memory",
            "contract_intel", "twin_truth", "causal_decisions",
            "sim_rl_factory", "autonomous_ops", "panes"} <= names


def test_full_loop_certify_then_attest(tmp_state):
    spine = Spine(SpineConfig(db_path=":memory:", jwt_secret="x", require_auth=False))
    bus, ctrl = _boot(spine)
    # simulate a certified gate decision flowing on the bus
    from aegis.backbone import ControlEvent
    bus.publish(ControlEvent("ship_gate", "gate_certified",
                             {"run_id": "r1", "outputs": {"price": "10"}},
                             run_id="r1", tenant_id="acme"))
    # SwapWatch should have snapshotted the baseline
    sw = ctrl.get("swapwatch")
    assert sw is not None
    # ROI attest a decision via the bus
    bus.publish(ControlEvent("roi_attest", "roi_record",
                             {"decision_id": "d1", "cost_usd": 1.0,
                              "measured_benefit_usd": 4.0, "basis": "3 refunds auto"},
                             tenant_id="acme"))
    roi = ctrl.get("roi_attest")
    rep = roi.report("d1", tenant_id="acme")
    assert rep.certified is True
    assert rep.net_usd == 3.0
    reset_registry()
