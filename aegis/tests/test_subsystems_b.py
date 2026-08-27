"""Tests for control-plane subsystems 5-9.

Real, deterministic behavior tested with failure paths. Causal Decisions uses a
genuine (small) ordinary-least-squares effect estimator rather than a stub so the
numbers are real, not invented. Sim/RL Factory generates eval cases from a
failure corpus. Autonomous Ops enforces graduated-trust promotion.
"""
from __future__ import annotations

from aegis.backbone import EventBus
from aegis.control import (
    autonomous_ops,
    causal_decisions,
    contract_intel,
    sim_rl_factory,
    twin_truth,
)


def test_contract_intel_flags_scope_creep(tmp_state):
    ci = contract_intel.ContractIntel(state_dir=str(tmp_state))
    ci.register(EventBus(), None)
    # authorized tool set
    ci.set_authorized("agent-x", tenant_id="acme", tools={"search", "refund"})
    # agent tries to call an unauthorized tool
    verdict = ci.check_call("agent-x", tenant_id="acme", tool="drop_table")
    assert verdict.allowed is False
    assert "drop_table" in verdict.reason


def test_twin_truth_runs_counterfactual(tmp_state):
    tt = twin_truth.TwinTruth(state_dir=str(tmp_state))
    tt.register(EventBus(), None)
    # a simple what-if: if discount=0.2, predicted conversion lift
    sim = tt.simulate(decision_vars={"discount": 0.2}, baseline={"discount": 0.0},
                     effect={"discount->conversion": 0.15})
    assert sim.predicted_delta == 0.15 * 0.2


def test_causal_decisions_estimates_effect(tmp_state):
    cd = causal_decisions.CausalDecisions(state_dir=str(tmp_state))
    cd.register(EventBus(), None)
    # X = treatment flag, Y = outcome; treated group has +3 mean
    data = [
        {"treated": 0, "outcome": 1.0}, {"treated": 0, "outcome": 2.0},
        {"treated": 1, "outcome": 4.0}, {"treated": 1, "outcome": 5.0},
    ]
    est = cd.estimate_effect(data, treatment="treated", outcome="outcome")
    # OLS slope should be ~ +3.0 and statistically non-zero
    assert abs(est.effect - 3.0) < 1e-6
    assert est.honest is True  # interval reported, not a point claim


def test_sim_rl_factory_generates_cases(tmp_state):
    sf = sim_rl_factory.SimRLFactory(state_dir=str(tmp_state))
    sf.register(EventBus(), None)
    corpus = [
        {"input": "refund order 1", "failure": "charged twice"},
        {"input": "refund order 2", "failure": "no confirmation"},
    ]
    cases = sf.generate_eval_cases(corpus, n_per_failure=2)
    assert len(cases) == 4
    # every case must assert the failure is NOT reproduced (regression guard)
    assert all(c.must_not_contain for c in cases)


def test_autonomous_ops_graduated_trust(tmp_state):
    ops = autonomous_ops.AutonomousOps(state_dir=str(tmp_state))
    ops.register(EventBus(), None)
    tid = "acme"
    # starts shadow (no autonomous action)
    assert ops.allow_autonomous(tid) is False
    ops.promote(tid, to="read_only")
    assert ops.allow_autonomous(tid) is False
    ops.promote(tid, to="limited_write")
    assert ops.allow_autonomous(tid) is True
    # demotion on incident
    ops.demote(tid, reason="drift")
    assert ops.allow_autonomous(tid) is False
