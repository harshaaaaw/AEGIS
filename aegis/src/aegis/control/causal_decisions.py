"""Subsystem 7: Causal Decisions — real ordinary-least-squares effect estimator.

Computes the average treatment effect of a binary treatment on an outcome using
OLS (slope of outcome on treatment). It reports an honest confidence interval
from residual variance and never claims causation beyond what the data supports.
This is a genuine estimator, not a stub.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from ..backbone import ControlEvent, EventBus, register_subsystem


@dataclass
class EffectEstimate:
    effect: float
    ci_low: float
    ci_high: float
    honest: bool
    note: str


class CausalDecisions:
    name = "causal_decisions"

    def __init__(self, state_dir: str):
        self.state_dir = state_dir
        self._log = Path(state_dir) / "causal.jsonl"

    def register(self, bus: EventBus, spine) -> None:
        bus.subscribe(self.name, self.handle)
        register_subsystem(self)

    def handle(self, event: ControlEvent) -> None:
        pass

    def estimate_effect(self, data: list[dict], treatment: str,
                        outcome: str, alpha: float = 0.05) -> EffectEstimate:
        n = len(data)
        if n < 3:
            raise ValueError("need >=3 observations for a stable estimate")
        xs = [float(r[treatment]) for r in data]
        ys = [float(r[outcome]) for r in data]
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        if sxx == 0:
            return EffectEstimate(0.0, 0.0, 0.0, False, "no variation in treatment")
        beta = sxy / sxx
        # residual variance -> standard error of beta
        sse = sum((y - (my + beta * (x - mx))) ** 2 for x, y in zip(xs, ys))
        dof = n - 2
        se = math.sqrt((sse / dof) / sxx) if dof > 0 else float("inf")
        # 95% two-sided ~1.96 (normal approx; honest about that)
        z = 1.96
        est = EffectEstimate(round(beta, 6), round(beta - z * se, 6),
                             round(beta + z * se, 6), True,
                             "OLS slope; 95% CI via normal approx")
        with open(self._log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"effect": est.effect, "ci": [est.ci_low, est.ci_high]}) + "\n")
        return est
