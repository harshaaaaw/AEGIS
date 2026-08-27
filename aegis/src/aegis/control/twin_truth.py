"""Subsystem 6: Twin Truth — digital-twin counterfactual simulation.

Given a baseline and an effect model, Twin Truth answers "what would the metric
look like if we changed decision_vars?" It is a deterministic linear simulator
(open about being a model, not a measurement) and persists the scenario.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..backbone import ControlEvent, EventBus, register_subsystem


@dataclass
class SimulationResult:
    predicted_delta: float
    scenario: dict
    honest_note: str = "model-based estimate, not a measurement"


class TwinTruth:
    name = "twin_truth"

    def __init__(self, state_dir: str):
        self.state_dir = state_dir
        self._log = Path(state_dir) / "twin.jsonl"

    def register(self, bus: EventBus, spine) -> None:
        bus.subscribe(self.name, self.handle)
        register_subsystem(self)

    def handle(self, event: ControlEvent) -> None:
        pass

    def simulate(self, decision_vars: dict, baseline: dict,
                 effect: dict) -> SimulationResult:
        """effect maps 'var->metric' to a coefficient. Linear, additive."""
        delta = 0.0
        for var, val in decision_vars.items():
            # match coefficient by the var name prefix in keys like 'discount->conversion'
            for k, c in effect.items():
                if k.startswith(f"{var}->"):
                    delta += c * float(val)
                    break
        res = SimulationResult(predicted_delta=round(delta, 6),
                               scenario={"decision_vars": decision_vars, "baseline": baseline})
        with open(self._log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"delta": res.predicted_delta, "scenario": res.scenario}) + "\n")
        return res
