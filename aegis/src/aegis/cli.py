"""Consumer-friendly AEGIS CLI.

Zero-config: no Kubernetes, no JWT, no secret. Runs entirely in-memory / temp
files so any engineer can reproduce a gate decision on their laptop in seconds.

    aegis certify  run.jsonl            # decide CERTIFY/BLOCK on a recorded run
    aegis verify   <verdict_id>         # re-check a verdict's signature + chain
    aegis drift    <run_id>             # SwapWatch: did behavior diverge?
    aegis posture  --tenant acme        # whole control-plane posture in one view
    aegis server   --port 8000          # optional: serve the HTTP API locally

A recorded run file is just JSONL of steps:
    {"idx":0,"kind":"MODEL_CALL","name":"planner","in":{...},"out":{...},"state":{...},"ms":5}
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import typer

from .backbone import EventBus, reset_registry
from .control import plane
from .control.swapwatch import SwapWatch
from .gate import GateRequest, ShipGate
from .security import is_ssrf_safe
from .spine import Spine, SpineConfig

app = typer.Typer(help="AEGIS: trust, govern, and prove enterprise agents.")


def _ephemeral() -> tuple[Spine, str]:
    """Stand up an in-memory spine + temp run dir so the CLI needs no setup."""
    d = Path(tempfile.mkdtemp(prefix="aegis-"))
    spine = Spine(SpineConfig(db_path=":memory:", jwt_secret="0" * 32,
                               require_auth=False))
    return spine, str(d / "runs")


def _load_run(path: str) -> list[dict]:
    # Resolve so POSIX-style and Windows relative paths both work for consumers.
    p = Path(path).expanduser().resolve()
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


@app.command()
def certify(run_file: str, tenant: str = "local", agent: str = "cli-agent",
            candidate: str = "local review"):
    """Decide CERTIFY/BLOCK for a recorded run JSONL file."""
    spine, state_dir = _ephemeral()
    run_id = spine.begin_run(agent_name=agent, tenant_id=tenant, idempotency_key=run_file)
    # copy the user's steps into the run-replay store the gate reads
    from run_replay import Recorder, RunMeta, StepKind  # type: ignore[import-untyped, attr-defined]
    rec = Recorder(state_dir=state_dir, meta=RunMeta(run_id=run_id, agent_name=agent))
    for step in _load_run(run_file):
        kind_raw = step.get("kind", "MODEL_CALL")
        # accept either the enum int value or its name string
        try:
            kind = StepKind(int(kind_raw))
        except (ValueError, TypeError):
            kind = StepKind[kind_raw]
        rec.step(kind, step.get("name", "step"),
                 inp=step.get("in", {}), out=step.get("out", {}),
                 state=step.get("state", {}), wall_ms=step.get("ms", 0.0))
    gate = ShipGate(spine, state_dir=state_dir)
    v = gate.evaluate(GateRequest(run_id=run_id, agent_name=agent,
                                  tenant_id=tenant, candidate_summary=candidate))
    typer.echo(json.dumps({"verdict_id": v.verdict_id, "decision": v.decision,
                           "reason": v.reason, "evidence": v.evidence,
                           "verify": f"aegis verify {v.verdict_id}"}, indent=2))


@app.command()
def verify(verdict_id: str, tenant: str = "local"):
    """Re-check a verdict's signature + hash-chain integrity."""
    spine, state_dir = _ephemeral()
    gate = ShipGate(spine, state_dir=state_dir)
    # the ledger lives in state_dir; if user ran certify elsewhere this is empty
    valid, rec = gate.verify_verdict(verdict_id, tenant_id=tenant)
    typer.echo(json.dumps({"verdict_id": verdict_id, "valid": valid,
                           "record": rec}, indent=2))


@app.command()
def drift(run_id: str, baseline: str, live: str):
    """SwapWatch: compare a live run's outputs to its certified baseline."""
    _spine, state_dir = _ephemeral()
    sw = SwapWatch(state_dir)
    base = _load_run(baseline)[-1].get("out", {})
    liv = _load_run(live)[-1].get("out", {})
    alert = sw.check_drift(run_id, baseline_digests=base, live_outputs=liv)
    typer.echo(json.dumps({"run_id": run_id, "drifted": alert.drifted,
                           "fields": alert.fields, "detail": alert.detail}, indent=2))


@app.command()
def posture(tenant: str = "local"):
    """Show the whole control-plane posture (trust tier, open drifts) in one view."""
    spine = Spine(SpineConfig(db_path=":memory:", jwt_secret="0" * 32,
                              require_auth=False))
    reset_registry()
    bus = EventBus()
    ctrl = plane.ControlPlane(spine, state_dir=tempfile.mkdtemp(prefix="aegis-"))
    ctrl.boot(bus)
    panes = ctrl.get("panes")
    if not isinstance(panes, plane.Panes):
        raise TypeError("panes room must be registered before posture")
    typer.echo(json.dumps(panes.posture(ctrl), indent=2))
    reset_registry()


@app.command()
def ssrf(url: str):
    """Check whether a URL is safe for an agent tool to fetch (SSRF guard)."""
    typer.echo(json.dumps({"url": url, "safe": is_ssrf_safe(url)}, indent=2))


@app.command()
def server(port: int = 8000):
    """Serve the HTTP API locally (needs a real secret; see SECURITY.md)."""
    import uvicorn

    from .main import build_app
    _spine, state_dir = _ephemeral()
    app_obj = build_app(db_path=":memory:", state_dir=state_dir, jwt_secret="0" * 32)
    uvicorn.run(app_obj, host="127.0.0.1", port=port)


if __name__ == "__main__":
    app()
