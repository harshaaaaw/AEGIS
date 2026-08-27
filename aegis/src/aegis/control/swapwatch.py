"""Subsystem 2: SwapWatch — behavior-drift detection.

Compares a live agent run against its certified baseline (the verdict the Ship
Gate already produced). If any field's live output diverges from the certified
value, SwapWatch raises a drift alert that is persisted to the Spine. This is
the "did the agent silently change its behavior after we certified it?" room.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..backbone import ControlEvent, EventBus, register_subsystem


@dataclass
class DriftAlert:
    run_id: str
    drifted: bool
    fields: list[str]
    detail: str


class SwapWatch:
    name = "swapwatch"

    def __init__(self, state_dir: str):
        self.state_dir = state_dir
        self._ledger = Path(state_dir) / "swapwatch.jsonl"

    def register(self, bus: EventBus, spine) -> None:
        bus.subscribe(self.name, self.handle)
        register_subsystem(self)

    def handle(self, event: ControlEvent) -> None:
        # React to gate certifications: snapshot the certified outputs as baseline.
        if event.kind == "gate_certified":
            outputs: dict[str, Any] = event.payload.get("outputs") or {}
            self._snapshot(event.run_id or "unknown", outputs)

    def _snapshot(self, run_id: str, outputs: dict) -> None:
        with open(self._ledger, "a", encoding="utf-8") as f:
            f.write(json.dumps({"run_id": run_id, "baseline": outputs}) + "\n")

    def check_drift(self, run_id: str, baseline_digests: dict,
                    live_outputs: dict) -> DriftAlert:
        """Compare live outputs to certified baseline values field-by-field."""
        drifted_fields: list[str] = []
        for field, base_val in baseline_digests.items():
            live_val = live_outputs.get(field)
            if live_val is None or str(live_val) != str(base_val):
                drifted_fields.append(field)
        alert = DriftAlert(
            run_id=run_id,
            drifted=bool(drifted_fields),
            fields=drifted_fields,
            detail=f"{len(drifted_fields)} field(s) diverged from certified baseline",
        )
        if alert.drifted:
            Path(self._ledger).parent.mkdir(parents=True, exist_ok=True)
            with open(self._ledger, "a", encoding="utf-8") as f:
                f.write(json.dumps({"run_id": run_id, "drift": drifted_fields}) + "\n")
        return alert
