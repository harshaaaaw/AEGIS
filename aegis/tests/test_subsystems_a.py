"""Tests for control-plane subsystems 2-4: SwapWatch, ROIAttest, GovernedMemory.

Each subsystem is a 'room' that consumes ControlEvents and persists evidence
to the Spine (externalized, tamper-evident). Tests are behavioral + failure-path.
"""
from __future__ import annotations

from aegis.backbone import EventBus
from aegis.control import governed_memory, roi_attest, swapwatch


def test_swapwatch_flags_behavior_drift(tmp_state):
    """When a live run diverges from its certified baseline, SwapWatch raises an alert."""
    from run_replay import Recorder, Replayer, RunMeta, StepKind
    run_id = "run-drift-1"
    base = Recorder(state_dir=str(tmp_state), meta=RunMeta(run_id=run_id, agent_name="pricer"))
    base.step(StepKind.MODEL_CALL, "planner", inp={"sku": "A"}, out={"price": 10},
              state={"price": 10}, wall_ms=5)
    _meta, events = base.load_run(base.path)
    baseline = Replayer(events).verify()

    # live run produces a different price (behavior drift)
    live = Recorder(state_dir=str(tmp_state), meta=RunMeta(run_id=run_id, agent_name="pricer"))
    live.step(StepKind.MODEL_CALL, "planner", inp={"sku": "A"}, out={"price": 999},
              state={"price": 999}, wall_ms=5)

    bus = EventBus()
    sw = swapwatch.SwapWatch(state_dir=str(tmp_state))
    sw.register(bus, None)
    # precondition: the recorded baseline replayed cleanly (no tamper/corruption)
    assert baseline.digests_match is True
    alert = sw.check_drift(run_id, baseline_digests={"price": "10"},
                           live_outputs={"price": "999"})
    assert alert.drifted is True
    assert "price" in alert.fields


def test_roi_attest_accumulates_and_certifies(spine):
    """ROI Attest records cost vs measured benefit and certifies when net-positive."""
    bus = EventBus()
    roi = roi_attest.ROIAttest(spine)
    roi.register(bus, spine)
    roi.record_decision("dec-1", tenant_id="acme", cost_usd=2.50,
                        measured_benefit_usd=8.00, basis="automated 3 refunds")
    rep = roi.report("dec-1", tenant_id="acme")
    assert rep.net_usd == 5.50
    assert rep.certified is True


def test_roi_attest_rejects_unattested_claim(spine):
    """A benefit with no measured basis must not be certified (anti-slop: no fake ROI)."""
    roi = roi_attest.ROIAttest(spine)
    roi.record_decision("dec-2", tenant_id="acme", cost_usd=1.0,
                        measured_benefit_usd=100.0, basis="")
    rep = roi.report("dec-2", tenant_id="acme")
    assert rep.certified is False
    assert "no basis" in rep.reason


def test_governed_memory_versioned_and_access_controlled(tmp_state):
    """Governed Memory: writes are versioned; reads require a capability the caller has."""
    mem = governed_memory.GovernedMemory(state_dir=str(tmp_state))
    v1 = mem.write("agent:prefs", tenant_id="acme", value={"tone": "formal"},
                   capabilities={"read:prefs"})
    v2 = mem.write("agent:prefs", tenant_id="acme", value={"tone": "casual"},
                   capabilities={"read:prefs"})
    assert v2.version == 2 and v2.version > v1.version
    # reader with the capability can read
    got = mem.read("agent:prefs", tenant_id="acme", capabilities={"read:prefs"})
    assert got.value["tone"] == "casual"
    # reader without capability is denied
    denied = mem.read("agent:prefs", tenant_id="acme", capabilities=set())
    assert denied is None
