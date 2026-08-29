"""Connect any agent CLI to the same Spine.

Each agent has its own command and a generic fallback:
  aegis agent claude  "task"
  aegis agent codex   "task"
  aegis agent hermes  "task"
  aegis agent openclaw "task"
  aegis agent generic --cmd "my-agent --flag" "task"

Output is recorded as a run, certified by Ship Gate, and signed.
If the real CLI is missing, a mock produces a verifiable run.
"""

from __future__ import annotations

import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..gate import GateRequest, ShipGate
from ..spine import Spine, SpineConfig


@dataclass
class AgentResult:
    agent: str
    command: str
    exit_code: int
    output: str
    verdict_id: str
    decision: str
    reason: str


@dataclass
class AgentSpec:
    name: str
    command: str
    args_template: list[str]


AGENTS: dict[str, AgentSpec] = {
    "claude": AgentSpec("claude", "claude", ["--print", "{task}"]),
    "codex": AgentSpec("codex", "codex", ["exec", "{task}"]),
    "hermes": AgentSpec("hermes", "hermes", ["agent", "{task}"]),
    "openclaw": AgentSpec("openclaw", "openclaw", ["run", "{task}"]),
}


def _run_cli(base: str, task: str, spec: AgentSpec | None, generic_cmd: str | None) -> tuple[int, str, str]:
    if generic_cmd:
        full = f"{generic_cmd} {shlex.quote(task)}"
        cmd = shlex.split(full)
        label = generic_cmd
    elif spec:
        arg = spec.args_template[-1].format(task=task)
        cmd = [spec.command, *spec.args_template[:-1], arg]
        label = f"{spec.command} {' '.join(spec.args_template).format(task=task)}"
    else:
        label = task
        cmd = [task]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60, check=False
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        if (proc.returncode != 0 and "not found" in out.lower()) or not out.strip():
            raise FileNotFoundError(label)
        return proc.returncode, out.strip()[:4000] or "(no output)", label
    except FileNotFoundError:
        mock = f"[mock:{base}] task: {task}\noutput: simulated agent output for consumer demo"
        return 0, mock, f"[mock] {base} {task}"
    except subprocess.TimeoutExpired:
        return 124, "[timeout] agent did not respond in 60s", label
    except Exception as e:  # noqa: BLE001 - consumer should not see crash
        return 1, f"[error] {e}", label


def run_agent(agent: str, task: str, tenant: str = "local", generic_cmd: str | None = None) -> AgentResult:
    spec = AGENTS.get(agent)
    base = agent if agent != "generic" else (generic_cmd or "generic")
    exit_code, output, command = _run_cli(base, task, spec, generic_cmd)
    tmp = Path(tempfile.mkdtemp(prefix="aegis-agent-"))
    state_dir = str(tmp / "runs")
    spine = Spine(SpineConfig(db_path=":memory:", jwt_secret="0" * 32, require_auth=False))
    run_id = spine.begin_run(agent_name=agent, tenant_id=tenant, idempotency_key=f"{agent}:{task[:80]}")
    from run_replay import Recorder, RunMeta, StepKind  # type: ignore

    rec = Recorder(state_dir=state_dir, meta=RunMeta(run_id=run_id, agent_name=agent))
    rec.step(
        StepKind.MODEL_CALL,
        "agent-output",
        inp={"task": task},
        out={"output": output, "exit_code": exit_code},
        state={"tenant": tenant},
        wall_ms=0.0,
    )
    gate = ShipGate(spine, state_dir=state_dir)
    verdict = gate.evaluate(
        GateRequest(run_id=run_id, agent_name=agent, tenant_id=tenant, candidate_summary=task[:120])
    )
    return AgentResult(
        agent=agent,
        command=command,
        exit_code=exit_code,
        output=output,
        verdict_id=verdict.verdict_id,
        decision=verdict.decision,
        reason=verdict.reason or "",
    )


def list_agents() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name, spec in AGENTS.items():
        rows.append(
            {"name": name, "command": f"{spec.command} {' '.join(spec.args_template)}", "kind": "native"}
        )
    rows.append(
        {"name": "generic", "command": 'aegis agent generic --cmd "<your CLI>" "task"', "kind": "any CLI"}
    )
    return rows
