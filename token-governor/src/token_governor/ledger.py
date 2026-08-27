"""Outcome ledger: cost per SUCCESSFUL outcome, not per call.

The board metric from the Agent FinOps literature: a workflow that costs
$0.50/call but fails 30% of the time costs $0.71 per success. This
ledger ties every billable call to its outcome id and rolls up:
  - cost per successful outcome (the number CFOs care about)
  - retry waste (money burned on failed attempts)
  - per-tenant / per-workflow margin tables

Append-only JSONL, one line per event; rollups are computed reads.
"""

from __future__ import annotations

import json
import os
import threading
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass
class OutcomeRollup:
    outcomes_total: int = 0
    outcomes_success: int = 0
    calls_total: int = 0
    cost_total_usd: float = 0.0
    retry_waste_usd: float = 0.0

    @property
    def cost_per_success_usd(self) -> float | None:
        return (self.cost_total_usd / self.outcomes_success
                if self.outcomes_success else None)

    @property
    def success_rate(self) -> float | None:
        return self.outcomes_success / self.outcomes_total if self.outcomes_total else None


class OutcomeLedger:
    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _append(self, event: dict):
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, separators=(",", ":")) + "\n")

    def record_call(self, session_id: str, ctx_ids: dict, model: str, cost_usd: float):
        self._append({"ev": "call", "session": session_id,
                      **ctx_ids, "model": model, "usd": round(cost_usd, 6)})

    def open_outcome(self, session_id: str, ctx_ids: dict):
        self._append({"ev": "open", "session": session_id, **ctx_ids})

    def close_outcome(self, session_id: str, ctx_ids: dict, success: bool):
        self._append({"ev": "close", "session": session_id,
                      "ok": success, **ctx_ids})

    # ---- rollups ------------------------------------------------------

    def rollup(self, tenant: str | None = None,
               workflow: str | None = None) -> OutcomeRollup:
        if not self.path.exists():
            return OutcomeRollup()
        # session -> state
        sessions: dict[str, dict] = defaultdict(
            lambda: {"calls": 0, "cost": 0.0, "tenant": "", "workflow": "",
                     "open": False, "ok": None})
        with self._lock, open(self.path, encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                s = sessions[e["session"]]
                s["tenant"] = e.get("tenant", s["tenant"])
                s["workflow"] = e.get("workflow", s["workflow"])
                if tenant and s["tenant"] != tenant:
                    continue
                if workflow and s["workflow"] != workflow:
                    continue
                if e["ev"] == "call":
                    s["calls"] += 1
                    s["cost"] += e["usd"]
                elif e["ev"] == "open":
                    s["open"] = True
                elif e["ev"] == "close":
                    s["open"] = False
                    s["ok"] = bool(e["ok"])

        r = OutcomeRollup()
        for s in sessions.values():
            if tenant and s["tenant"] != tenant:
                continue
            if workflow and s["workflow"] != workflow:
                continue
            r.calls_total += s["calls"]
            r.cost_total_usd += s["cost"]
            if s["ok"] is not None:                 # closed outcome
                r.outcomes_total += 1
                r.retry_waste_usd += 0.0 if s["ok"] else s["cost"]
                if s["ok"]:
                    r.outcomes_success += 1
        return r
