"""Subsystem 8: Sim/RL Factory — synthesize eval cases from failure corpora.

Given a corpus of real failures (input + observed failure), generate eval cases
that assert the failure is NOT reproduced. This feeds the Ship Gate's evalforge
golden set, closing the loop: production failures become regression tests.
"""
from __future__ import annotations

import json
from pathlib import Path

from evalforge import EvalCase  # type: ignore

from ..backbone import ControlEvent, EventBus, register_subsystem


class SimRLFactory:
    name = "sim_rl_factory"

    def __init__(self, state_dir: str):
        self.state_dir = state_dir
        self._log = Path(state_dir) / "simrl.jsonl"

    def register(self, bus: EventBus, spine) -> None:
        bus.subscribe(self.name, self.handle)
        register_subsystem(self)

    def handle(self, event: ControlEvent) -> None:
        pass

    def generate_eval_cases(self, corpus: list[dict], n_per_failure: int = 1) -> list[EvalCase]:
        cases: list[EvalCase] = []
        for i, item in enumerate(corpus):
            inp = item.get("input", "")
            failure = item.get("failure", "regression")
            for k in range(n_per_failure):
                case = EvalCase(
                    case_id=f"sim-{i}-{k}",
                    input=inp,
                    must_not_contain=[failure],
                    require_citation=False,
                )
                cases.append(case)
                with open(self._log, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"case_id": case.case_id, "failure": failure}) + "\n")
        return cases
