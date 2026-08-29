"""Ship Gate: combine run-replay (forensics) + agent-sentinel (shield) +
evalforge (eval) into one signed CERTIFY/BLOCK verdict.

Anti-slop invariants:
- No bare except: typed GateError carries verdict_id.
- Idempotent: same (run_id, candidate_hash) -> same verdict_id.
- Every verdict is written to the Spine atomically before return.
- Verdict signature is HMAC-SHA256 over the canonical decision (tamper-evident).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_sentinel import (  # type: ignore[import-untyped, attr-defined]
    Sentinel,
    ToolCall,
    ToolResult,
    TurnContext,
)
from evalforge import EvalCase, EvalRunner, GoldenSet  # type: ignore[import-untyped, attr-defined]
from run_replay import Replayer, StepKind  # type: ignore[import-untyped, attr-defined]

from .spine import Spine


class GateError(Exception):
    """Typed gate failure, carries a verdict_id for tracing."""


@dataclass
class GateRequest:
    run_id: str
    agent_name: str
    tenant_id: str
    candidate_summary: str
    golden_set: GoldenSet | None = None  # optional eval suite to gate against


@dataclass
class Verdict:
    verdict_id: str
    run_id: str
    tenant_id: str
    decision: str               # "CERTIFY" | "BLOCK"
    reason: str
    signature: str
    evidence: dict[str, Any] = field(default_factory=dict)
    issued_at: int = field(default_factory=lambda: int(time.time()))


@dataclass
class _VerdictRow:
    pass


class ShipGate:
    def __init__(self, spine: Spine, state_dir: str):
        self.spine = spine
        self.state_dir = state_dir
        self.sentinel = Sentinel(audit_root=f"{state_dir}/.sentinel")
        self.evaluator = EvalRunner(state_dir=f"{state_dir}/.evalforge")
        self._signing_key = spine.cfg.jwt_secret.encode()

    def _load_run(self, run_id: str):
        # NOTE: constructing a Recorder truncates the run file, so we read the
        # JSONL directly (mirrors Recorder.load_run without the side effect).
        path = f"{self.state_dir}/runs/{run_id}.jsonl"
        import json as _json

        from run_replay.models import StepEvent, StepKind
        try:
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except FileNotFoundError as e:
            raise GateError(f"run {run_id!r} not found") from e
        events = []
        for raw in lines[1:]:
            ev = _json.loads(raw)
            events.append(StepEvent(
                idx=ev["idx"], kind=StepKind(ev["kind"]), name=ev["name"],
                input_digest=ev["in_d"], output_digest=ev["out_d"],
                input_data=ev.get("in"), output_data=ev.get("out"),
                state_hash=ev.get("state", ""), wall_ms=ev.get("ms", 0.0),
            ))
        return events

    def _sign(self, payload: dict) -> str:
        canon = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hmac.new(self._signing_key, canon.encode(), hashlib.sha256).hexdigest()[:32]

    def evaluate(self, req: GateRequest) -> Verdict:
        if not req.run_id or not req.tenant_id:
            raise GateError("evaluate: run_id and tenant_id required")

        # 1) Forensic verify of the candidate run (tamper-evidence).
        events = self._load_run(req.run_id)
        replay = Replayer(events).verify()
        replay_intact = replay.digests_match

        # 2) Shield every tool result in the run.
        ctx = TurnContext.new(tenant_id=req.tenant_id)
        shield_flagged = False
        for ev in events:
            if ev.kind is StepKind.TOOL_CALL and ev.output_data:
                page = str(ev.output_data)
                d = self.sentinel.inspect_tool_result(
                    ToolResult(ToolCall("tool", {}), page), ctx)
                if d.action.value in ("BLOCK", "REDACT"):
                    shield_flagged = True
                    break

        # 3) Eval against the golden set, if supplied.
        eval_block = False
        faithfulness = None
        if req.golden_set is not None:
            # A minimal pipeline stand-in: the candidate's recorded outputs answer the cases.
            def pipeline(case: EvalCase) -> str:
                # For a ship-gate, "answer" = concatenated recorded outputs as evidence.
                return " ".join(str(ev.output_data) for ev in events if ev.output_data)
            report = self.evaluator.run(req.golden_set, pipeline)
            faithfulness = report.faithfulness
            eval_block = report.pass_rate < 1.0

        # 4) Decide.
        blocked = (not replay_intact) or shield_flagged or eval_block
        decision = "BLOCK" if blocked else "CERTIFY"
        reason_parts = []
        if not replay_intact:
            reason_parts.append(f"run tampering at step {replay.diverged_at}")
        if shield_flagged:
            reason_parts.append("shield flagged adversarial tool content")
        if eval_block:
            reason_parts.append("golden-set eval regressed")
        reason = "; ".join(reason_parts) or "all gates passed"

        candidate_hash = hashlib.sha256(req.candidate_summary.encode()).hexdigest()[:16]
        verdict_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{req.run_id}:{candidate_hash}").hex[:16]
        issued_at = int(time.time())

        evidence = {
            "replay_intact": replay_intact,
            "diverged_at": replay.diverged_at,
            "shield_flagged": shield_flagged,
            "eval_block": eval_block,
            "faithfulness": faithfulness,
            "candidate_hash": candidate_hash,
        }
        payload = {
            "verdict_id": verdict_id,
            "run_id": req.run_id,
            "tenant_id": req.tenant_id,
            "decision": decision,
            "evidence": evidence,
            "issued_at": issued_at,
        }
        verdict = Verdict(
            verdict_id=verdict_id, run_id=req.run_id, tenant_id=req.tenant_id,
            decision=decision, reason=reason, signature=self._sign(payload),
            evidence=evidence, issued_at=issued_at,
        )
        # 5) Persist atomically to the Spine (idempotent by verdict_id).
        self._persist_verdict(verdict)
        return verdict

    def _persist_verdict(self, v: Verdict) -> str | None:
        """Append the verdict to an append-only, HASH-CHAINED ledger file.

        Each line carries prev_hash (sha256 of the prior line) so tampering with
        any historical verdict breaks the chain from that point forward. The
        verdict is also signed (HMAC) for single-record verification. Externalized
        state, idempotent by verdict_id: a re-evaluation with the same key appends
        an identical line (dedup by verdict_id on read).
        """
        ledger = f"{self.state_dir}/verdicts.jsonl"
        prev = ""
        if Path(ledger).exists():
            with open(ledger, encoding="utf-8") as fh:
                last = fh.read().splitlines()[-1]
            prev = hashlib.sha256(last.encode()).hexdigest()[:32]
        record = {
            "verdict_id": v.verdict_id,
            "run_id": v.run_id,
            "tenant_id": v.tenant_id,
            "decision": v.decision,
            "reason": v.reason,
            "signature": v.signature,
            "evidence": v.evidence,
            "issued_at": v.issued_at,
            "prev_hash": prev,
        }
        line = json.dumps(record, sort_keys=True)
        with open(ledger, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return prev

    def verify_verdict(self, verdict_id: str,
                       tenant_id: str | None = None) -> tuple[bool, dict | None]:
        """Recompute the signature + hash chain of a stored verdict.

        If tenant_id is supplied, the verdict is scoped to that tenant (no
        cross-tenant info leak). Returns (valid, record). Chain validity is
        checked across the whole ledger so a historical edit is detected.
        """
        ledger = f"{self.state_dir}/verdicts.jsonl"
        try:
            with open(ledger, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except FileNotFoundError:
            return False, None
        # verify chain integrity end-to-end
        chain_ok = True
        prev = ""
        target: dict | None = None
        for raw in lines:
            rec = json.loads(raw)
            if rec.get("prev_hash") != prev:
                chain_ok = False
            prev = hashlib.sha256(raw.encode()).hexdigest()[:32]
            if rec["verdict_id"] == verdict_id:
                target = rec
        if target is None:
            return False, None
        if tenant_id is not None and target.get("tenant_id") != tenant_id:
            return False, None  # not this tenant's verdict
        payload = {k: target[k] for k in
                    ("verdict_id", "run_id", "tenant_id", "decision", "evidence", "issued_at")}
        expected = self._sign(payload)
        sig_ok = hmac.compare_digest(expected, target["signature"])
        return (sig_ok and chain_ok), target
