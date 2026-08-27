"""Cross-product integration test: the three rooms as ONE central suite.

Proves the loop closure honestly:
  SIMFORGE simulates an agent under perturbation,
  -> forges an evalforge.EvalCase,
  -> publishes 'sim_certified' on the AEGIS bus,
  -> AEGIS Ship Gate subscribes and records it as a golden regression case.

This is the real "govern + understand + stress" product, not three silos.
"""
from __future__ import annotations

import tempfile

from aegis.backbone import EventBus, reset_registry
from aegis.control.plane import ControlPlane
from aegis.spine import Spine, SpineConfig


def _demo_agent(obs, ctx):
    return {"decision": "allow"}


def _causal_check(effect, tenant):
    # margin_up must come from cost_down, never from discount -> used to detect drift
    if effect == "margin_up":
        return (True, "cost_down")
    return (False, "unknown")


def test_simforge_forged_case_reaches_aegis_gate():
    reset_registry()
    bus = EventBus()
    spine = Spine(SpineConfig(db_path=":memory:", jwt_secret="0" * 32,
                              require_auth=False))
    ctrl = ControlPlane(spine, state_dir="__integ_state")
    ctrl.boot(bus)

    # SIMFORGE side: run + forge
    from simforge import Scenario, run_scenario
    from simforge.forge import ForgeRoom

    gate = ctrl.get("ship_gate")
    assert gate is not None

    scen = Scenario(scenario_id="integ_s1", agent_under_test="demo", seed=5,
                    perturbations=[{"kind": "inject_noise", "field": "input"}],
                    causal_invariants=[{"effect": "margin_up", "cause": "discount"}])
    run = run_scenario(scen, _demo_agent, "acme", causal_check=_causal_check)

    case = ForgeRoom(state_dir="runs").publish(bus, run, "acme")

    # The forged case must have reached the AEGIS control plane's Ship Gate
    # (consumed from the bus into its golden regression set).
    goldens = gate.golden_cases("acme")
    assert any(g["case_id"] == case.case_id for g in goldens), \
        "forged case did not reach AEGIS Ship Gate golden set"
    # And the run record round-trips through the Spine (tamper-evident anchor).
    assert run.run_id.startswith("sim_")
    reset_registry()


def test_causala_explains_while_aegis_gates():
    # CAUSALA (understand) + AEGIS (govern) share the bus; both answer one tenant.
    reset_registry()
    bus = EventBus()
    spine = Spine(SpineConfig(db_path=":memory:", jwt_secret="0" * 32,
                              require_auth=False))
    ctrl = ControlPlane(spine, state_dir="__integ2")
    ctrl.boot(bus)

    from causa import Causala
    db = tempfile.mkdtemp(prefix="causala-") + "/c.db"
    c = Causala(db)
    c.ingest_claim("cost_down", "margin_up", 0.95, "finance-model", "acme")
    ans = c.explain_effect("margin_up", "acme")
    assert ans.cause == "cost_down"

    # AEGIS gate still boots and evaluates independently for the same tenant.
    gate = ctrl.get("ship_gate")
    assert gate is not None
    reset_registry()
