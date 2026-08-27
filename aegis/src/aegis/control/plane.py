"""Subsystem 10 + orchestrator: the room where all 10 subsystems live.

`ControlPlane.boot(bus)` instantiates every subsystem, registers it on the bus,
and exposes them by name. `Panes` is the tenth room: a read-only view/aggregator
that surfaces each subsystem's latest posture (trust tier, open drifts, attested
ROI) so an operator can see the whole control plane in one place.
"""
from __future__ import annotations

from pathlib import Path

from ..backbone import ControlEvent, EventBus, Subsystem, register_subsystem
from ..security import get_logger
from .autonomous_ops import AutonomousOps
from .causal_decisions import CausalDecisions
from .contract_intel import ContractIntel
from .governed_memory import GovernedMemory
from .roi_attest import ROIAttest
from .sim_rl_factory import SimRLFactory
from .swapwatch import SwapWatch
from .twin_truth import TwinTruth

log = get_logger("aegis.plane")


class Panes:
    name = "panes"

    def __init__(self, state_dir: str):
        self.state_dir = state_dir

    def register(self, bus: EventBus, spine) -> None:
        register_subsystem(self)

    def handle(self, event) -> None:
        # Panes is a read-only aggregator; it does not react to bus events.
        return None

    def posture(self, control: ControlPlane) -> dict:
        out: dict[str, object] = {}
        ops = control.get("autonomous_ops")
        if isinstance(ops, AutonomousOps):
            out["trust_tiers"] = dict(ops._tiers)
        sw = control.get("swapwatch")
        if isinstance(sw, SwapWatch):
            drifts = 0
            if Path(sw._ledger).exists():
                for raw in Path(sw._ledger).read_text(encoding="utf-8").splitlines():
                    if "drift" in raw:
                        drifts += 1
            out["open_drifts"] = drifts
        return out


class ControlPlane:
    def __init__(self, spine, state_dir: str):
        self.spine = spine
        self.state_dir = state_dir
        self.subsystems: list[Subsystem] = []
        self._by_name: dict[str, Subsystem] = {}

    def boot(self, bus: EventBus) -> None:
        # The ten rooms of the control plane.
        self.subsystems = [
            SwapWatch(self.state_dir),
            ROIAttest(self.spine),
            GovernedMemory(self.state_dir),
            ContractIntel(self.state_dir),
            TwinTruth(self.state_dir),
            CausalDecisions(self.state_dir),
            SimRLFactory(self.state_dir),
            AutonomousOps(self.state_dir),
            Panes(self.state_dir),
            # ship_gate is the API-layer gate (aegis.gate.ShipGate); register a
            # bus-facing adapter so it appears as a room too.
            _GateRoom(self.spine, self.state_dir),
        ]
        for s in self.subsystems:
            s.register(bus, self.spine)
            self._by_name[s.name] = s

    def get(self, name: str) -> Subsystem | None:
        return self._by_name.get(name)


class _GateRoom:
    """Bus-facing adapter so the Ship Gate is also a first-class room."""

    name = "ship_gate"

    def __init__(self, spine, state_dir: str):
        from ..gate import ShipGate
        self._gate = ShipGate(spine, state_dir=state_dir)
        self._golden: list[dict] = []  # sim-forged regression cases consumed from SIMFORGE

    def register(self, bus: EventBus, spine) -> None:
        register_subsystem(self)
        # Consume SIMFORGE's forged golden cases so the Ship Gate's eval set is
        # closed-loop: production sim failures become regression guards.
        bus.subscribe("sim_forge", self.handle_sim_certified)

    def handle(self, event) -> None:
        # The gate room reacts to gate_certified (no-op here; verdicts are
        # created via evaluate()). Present so it satisfies the Subsystem protocol.
        return None

    def handle_sim_certified(self, event: ControlEvent) -> None:
        # Record the forged golden case; the Ship Gate consults this set before
        # certifying a deploy (a case that a prior sim failed must pass now).
        self._golden.append({
            "case_id": event.payload.get("case_id"),
            "run_id": event.payload.get("run_id"),
            "tenant_id": event.tenant_id,
            "asserts_failed": event.payload.get("asserts_failed"),
        })
        log.info("sim_golden_consumed", extra={"case_id": event.payload.get("case_id"),
                                               "tenant": event.tenant_id})

    def golden_cases(self, tenant_id: str | None = None) -> list[dict]:
        if tenant_id is None:
            return list(self._golden)
        return [g for g in self._golden if g["tenant_id"] == tenant_id]
