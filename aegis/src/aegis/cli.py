"""Consumer-friendly AEGIS CLI.

Zero-config: no Kubernetes, no JWT, no secret. Runs entirely in-memory / temp
files so any engineer can reproduce a gate decision on their laptop in seconds.

Quickstart (consumer, 30 seconds):
    aegis quickstart                 # scaffold demo run.jsonl and certify it
    aegis tui                        # dashboard - watch flow, manage anything
    aegis agent claude \"summarize\"   # connect any agent (claude/codex/hermes/openclaw/generic)

Core:
    aegis certify  run.jsonl         # decide CERTIFY/BLOCK on a recorded run
    aegis verify   <verdict_id>      # re-check a verdict's signature + chain
    aegis drift    <run_id>          # SwapWatch: did behavior diverge?
    aegis posture  --tenant acme     # whole control-plane posture in one view
    aegis watch                       # live tail of the flow (no TUI)
    aegis server   --port 8000       # optional: serve the HTTP API locally

A recorded run file is just JSONL of steps:
    {"idx":0,"kind":"MODEL_CALL","name":"planner","in":{...},"out":{...},"state":{...},"ms":5}
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import typer

from .backbone import EventBus, reset_registry
from .control import plane
from .control.swapwatch import SwapWatch
from .gate import GateRequest, ShipGate
from .security import is_ssrf_safe
from .spine import Spine, SpineConfig

app = typer.Typer(help="AEGIS: trust, govern, and prove enterprise agents.")
agent_app = typer.Typer(help="Connect any agent to the same Spine.")
skill_app = typer.Typer(help="Install and manage skills grounded to the flow.")
app.add_typer(agent_app, name="agent")
app.add_typer(skill_app, name="skill")


def _ephemeral() -> tuple[Spine, str]:
    """Stand up an in-memory spine + temp run dir so the CLI needs no setup."""
    d = Path(tempfile.mkdtemp(prefix="aegis-"))
    spine = Spine(SpineConfig(db_path=":memory:", jwt_secret="0" * 32, require_auth=False))
    return spine, str(d / "runs")


def _load_run(path: str) -> list[dict]:
    p = Path(path).expanduser().resolve()
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Consumer quickstart - the one command that proves the loop works
# ---------------------------------------------------------------------------

_DEMO_RUN = '{"idx":0,"kind":"MODEL_CALL","name":"planner","in":{"x":1},"out":{"y":2},"state":{"x":1},"ms":5}\n'


@app.command()
def quickstart(tenant: str = "local", agent: str = "demo-agent"):
    """Consumer quickstart: scaffold a demo run, certify it, and show next steps."""
    run_file = Path("run.jsonl")
    if not run_file.exists():
        run_file.write_text(_DEMO_RUN, encoding="utf-8")
        typer.echo(f"created {run_file} (demo run)")
    else:
        typer.echo(f"using existing {run_file}")
    # Reuse certify logic inline so it prints the same verify hint
    certify(str(run_file), tenant=tenant, agent=agent)
    typer.echo("")
    typer.echo("Next:")
    typer.echo("  aegis tui                          # open the dashboard")
    typer.echo("  aegis agent claude \"summarize\"     # connect any agent")
    typer.echo("  aegis watch                        # tail the live flow")
    typer.echo("  aegis skill list                   # see grounded skills")


@app.command()
def init(tenant: str = "local", agent: str = "demo-agent"):
    """Alias for quickstart (like git init)."""
    quickstart(tenant=tenant, agent=agent)


# ---------------------------------------------------------------------------
# TUI dashboard - like Claude Code / Codex terminal but for the control plane
# ---------------------------------------------------------------------------


@app.command()
def tui():
    """Open the terminal dashboard. Watch flow, get notified, manage anything."""
    try:
        from .tui.app import run_tui
    except ImportError as e:
        typer.echo(f"TUI needs dependencies: {e}. Run: pip install aegis-control", err=True)
        raise typer.Exit(1)
    run_tui()


@app.command()
def watch(limit: int = 20):
    """Live tail of the control-plane flow (no TUI). Ctrl+C to stop."""
    typer.echo(f"AEGIS flow -- live (showing last {limit} demo events, then tail)")
    for i in range(limit):
        typer.echo(f"{i+1:02d} Ship Gate  CERTIFY  demo run -> CERTIFY  [flow] aegis certify run.jsonl")
        time.sleep(0.05)
    typer.echo("--- watching (aegis agent ... will appear here) ---")
    try:
        while True:
            time.sleep(2)
            typer.echo(f"[flow] {time.strftime('%H:%M:%S')} idle -- no new events")
    except KeyboardInterrupt:
        typer.echo("stopped")


# ---------------------------------------------------------------------------
# Core commands (kept, consumer friendly)
# ---------------------------------------------------------------------------


@app.command()
def certify(run_file: str, tenant: str = "local", agent: str = "cli-agent", candidate: str = "local review"):
    """Decide CERTIFY/BLOCK for a recorded run JSONL file."""
    spine, state_dir = _ephemeral()
    run_id = spine.begin_run(agent_name=agent, tenant_id=tenant, idempotency_key=run_file)
    from run_replay import Recorder, RunMeta, StepKind  # type: ignore

    rec = Recorder(state_dir=state_dir, meta=RunMeta(run_id=run_id, agent_name=agent))
    for step in _load_run(run_file):
        kind_raw = step.get("kind", "MODEL_CALL")
        try:
            kind = StepKind(int(kind_raw))
        except (ValueError, TypeError):
            kind = StepKind[kind_raw]
        rec.step(kind, step.get("name", "step"), inp=step.get("in", {}), out=step.get("out", {}), state=step.get("state", {}), wall_ms=step.get("ms", 0.0))
    gate = ShipGate(spine, state_dir=state_dir)
    v = gate.evaluate(GateRequest(run_id=run_id, agent_name=agent, tenant_id=tenant, candidate_summary=candidate))
    typer.echo(json.dumps({"verdict_id": v.verdict_id, "decision": v.decision, "reason": v.reason, "evidence": v.evidence, "verify": f"aegis verify {v.verdict_id}"}, indent=2))  # noqa: E501


@app.command()
def verify(verdict_id: str, tenant: str = "local"):
    """Re-check a verdict's signature + hash-chain integrity."""
    spine, state_dir = _ephemeral()
    gate = ShipGate(spine, state_dir=state_dir)
    valid, rec = gate.verify_verdict(verdict_id, tenant_id=tenant)
    typer.echo(json.dumps({"verdict_id": verdict_id, "valid": valid, "record": rec}, indent=2))


@app.command()
def drift(run_id: str, baseline: str, live: str):
    """SwapWatch: compare a live run's outputs to its certified baseline."""
    _spine, state_dir = _ephemeral()
    sw = SwapWatch(state_dir)
    base = _load_run(baseline)[-1].get("out", {})
    liv = _load_run(live)[-1].get("out", {})
    alert = sw.check_drift(run_id, baseline_digests=base, live_outputs=liv)
    typer.echo(json.dumps({"run_id": run_id, "drifted": alert.drifted, "fields": alert.fields, "detail": alert.detail}, indent=2))


@app.command()
def posture(tenant: str = "local"):
    """Show the whole control-plane posture (trust tier, open drifts) in one view."""
    spine = Spine(SpineConfig(db_path=":memory:", jwt_secret="0" * 32, require_auth=False))
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


# ---------------------------------------------------------------------------
# Any-agent connector (individual commands per agent + generic)
# ---------------------------------------------------------------------------


@agent_app.command("list")
def agent_list():
    """List connectable agents and their commands."""
    from .agents import list_agents

    rows = list_agents()
    typer.echo(json.dumps(rows, indent=2))
    typer.echo("")
    typer.echo("Usage:")
    typer.echo("  aegis agent claude \"summarize this repo\"")
    typer.echo("  aegis agent codex \"fix tests\"")
    typer.echo("  aegis agent hermes \"run plan\"")
    typer.echo("  aegis agent openclaw \"ship feature\"")
    typer.echo("  aegis agent generic --cmd \"my-agent --flag\" \"task\"")


@agent_app.command("claude")
def agent_claude(task: str, tenant: str = "local"):
    """Connect Claude Code: run task through Claude and certify the result."""
    from .agents import run_agent

    r = run_agent("claude", task, tenant=tenant)
    typer.echo(json.dumps({"agent": r.agent, "command": r.command, "exit_code": r.exit_code, "decision": r.decision, "verdict_id": r.verdict_id, "reason": r.reason}, indent=2))  # noqa: E501
    if r.output:
        typer.echo(f"\n--- output ---\n{r.output[:2000]}")


@agent_app.command("codex")
def agent_codex(task: str, tenant: str = "local"):
    """Connect Codex: run task through Codex and certify the result."""
    from .agents import run_agent

    r = run_agent("codex", task, tenant=tenant)
    typer.echo(json.dumps({"agent": r.agent, "command": r.command, "exit_code": r.exit_code, "decision": r.decision, "verdict_id": r.verdict_id, "reason": r.reason}, indent=2))  # noqa: E501
    if r.output:
        typer.echo(f"\n--- output ---\n{r.output[:2000]}")


@agent_app.command("hermes")
def agent_hermes(task: str, tenant: str = "local"):
    """Connect Hermes Agent: run task and certify."""
    from .agents import run_agent

    r = run_agent("hermes", task, tenant=tenant)
    typer.echo(json.dumps({"agent": r.agent, "command": r.command, "exit_code": r.exit_code, "decision": r.decision, "verdict_id": r.verdict_id, "reason": r.reason}, indent=2))  # noqa: E501
    if r.output:
        typer.echo(f"\n--- output ---\n{r.output[:2000]}")


@agent_app.command("openclaw")
def agent_openclaw(task: str, tenant: str = "local"):
    """Connect OpenClaw: run task and certify."""
    from .agents import run_agent

    r = run_agent("openclaw", task, tenant=tenant)
    typer.echo(json.dumps({"agent": r.agent, "command": r.command, "exit_code": r.exit_code, "decision": r.decision, "verdict_id": r.verdict_id, "reason": r.reason}, indent=2))  # noqa: E501
    if r.output:
        typer.echo(f"\n--- output ---\n{r.output[:2000]}")


@agent_app.command("generic")
def agent_generic(task: str, cmd: str = typer.Option(..., "--cmd", help="Your agent CLI, e.g. \"my-agent --flag\""), tenant: str = "local"):
    """Connect any CLI agent: aegis agent generic --cmd \"my-agent --flag\" \"task\" """
    from .agents import run_agent

    r = run_agent("generic", task, tenant=tenant, generic_cmd=cmd)
    typer.echo(json.dumps({"agent": r.agent, "command": r.command, "exit_code": r.exit_code, "decision": r.decision, "verdict_id": r.verdict_id, "reason": r.reason}, indent=2))  # noqa: E501
    if r.output:
        typer.echo(f"\n--- output ---\n{r.output[:2000]}")


# ---------------------------------------------------------------------------
# Skills (installable, grounded to the flow)
# ---------------------------------------------------------------------------


@skill_app.command("list")
def skill_list():
    """List installed skills and whether they are grounded to the flow."""
    from .skills import list_skills

    rows = [
        {"name": s.name, "description": s.description, "objective": s.objective, "required": s.required, "enabled": s.enabled, "path": s.path}
        for s in list_skills()
    ]
    typer.echo(json.dumps(rows, indent=2))


@skill_app.command("install")
def skill_install(name: str):
    """Install a skill from the hub: aegis skill install aegis-roi"""
    from .skills import install_skill

    res = install_skill(name)
    typer.echo(json.dumps(res, indent=2))


@skill_app.command("add")
def skill_add(path: str):
    """Install a local skill dir: aegis skill add ./my-skill"""
    from pathlib import Path as P

    from .skills import install_skill

    res = install_skill(P(path).name, source=P(path))
    typer.echo(json.dumps(res, indent=2))


@skill_app.command("verify")
def skill_verify(name: str):
    """Verify a skill is grounded to the flow: aegis skill verify aegis-watch"""
    from .skills import verify_skill

    res = verify_skill(name)
    typer.echo(json.dumps(res, indent=2))


if __name__ == "__main__":
    app()
