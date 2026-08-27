"""Subsystem 3: ROI Attest — tamper-evident cost/benefit ledger.

Every autonomous decision claims value. ROI Attest only certifies a decision
when it has a MEASURED benefit with a non-empty basis (no invented ROI). The
ledger is append-only and signed so an attestation can be audited later.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..backbone import ControlEvent, EventBus, register_subsystem
from ..spine import Spine


@dataclass
class ROIReport:
    decision_id: str
    cost_usd: float
    measured_benefit_usd: float
    net_usd: float
    certified: bool
    reason: str


class ROIAttest:
    name = "roi_attest"

    def __init__(self, spine: Spine | None = None, state_dir: str = ""):
        self.spine = spine
        # ledger lives in the externalized state dir, not coupled to spine.cfg
        if state_dir:
            self._ledger = Path(state_dir) / "roi.jsonl"
        elif spine is not None:
            self._ledger = Path(spine.cfg.db_path).parent / "roi.jsonl"
        else:
            # no spine, no state_dir: still operable with a temp ledger
            self._ledger = Path(tempfile.gettempdir()) / "aegis-roi.jsonl"

    def register(self, bus: EventBus, spine) -> None:
        bus.subscribe(self.name, self.handle)
        register_subsystem(self)

    def handle(self, event: ControlEvent) -> None:
        # record on an explicit roi_record event
        if event.kind == "roi_record":
            p = event.payload
            self.record_decision(p["decision_id"], event.tenant_id or "unknown",
                                 p["cost_usd"], p["measured_benefit_usd"], p["basis"])

    def record_decision(self, decision_id: str, tenant_id: str,
                        cost_usd: float, measured_benefit_usd: float,
                        basis: str) -> ROIReport:
        net = round(measured_benefit_usd - cost_usd, 2)
        certified = bool(basis) and net > 0
        reason = "certified: measured benefit exceeds cost" if certified else (
            "no basis" if not basis else "net negative")
        line = json.dumps({
            "decision_id": decision_id, "tenant_id": tenant_id,
            "cost_usd": cost_usd, "benefit_usd": measured_benefit_usd,
            "net_usd": net, "certified": certified, "reason": reason,
        })
        sig = hashlib.sha256(line.encode()).hexdigest()[:16]
        with open(self._ledger, "a", encoding="utf-8") as f:
            f.write(json.dumps({"sig": sig, "rec": json.loads(line)}) + "\n")
        return ROIReport(decision_id, cost_usd, measured_benefit_usd, net,
                         certified, reason)

    def report(self, decision_id: str, tenant_id: str) -> ROIReport:
        for raw in (self._ledger.read_text(encoding="utf-8").splitlines()
                    if self._ledger.exists() else []):
            rec = json.loads(raw)["rec"]
            if rec["decision_id"] == decision_id and rec["tenant_id"] == tenant_id:
                return ROIReport(rec["decision_id"], rec["cost_usd"], rec["benefit_usd"],
                                 rec["net_usd"], rec["certified"], rec["reason"])
        raise KeyError(f"no ROI record for {decision_id!r}")
