"""Core models for meshwork."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Task:
    """One unit of work flowing between agents."""
    payload: dict
    meta: dict = field(default_factory=dict)
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])


@dataclass
class StepResult:
    agent_name: str
    output: dict | None          # None means the step failed
    error: str | None = None
    latency_ms: float = 0.0


@dataclass
class RunState:
    """Checkpointable state of one workflow run."""
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    workflow_name: str = ""
    step_idx: int = 0
    current_task: Task | None = None
    history: list[StepResult] = field(default_factory=list)
    artifacts: dict = field(default_factory=dict)     # shared scratchpad
    started: float = field(default_factory=time.time)
    finished: float | None = None
    status: str = "running"                            # running|done|failed|awaiting_human


class Checkpoint:
    """Serialize/deserialize RunState. JSON-only so it can live anywhere:
    a file, Redis, S3, a database row."""

    @staticmethod
    def save(state: RunState) -> dict:
        return {
            "run_id": state.run_id,
            "workflow": state.workflow_name,
            "step_idx": state.step_idx,
            "task_payload": state.current_task.payload if state.current_task else None,
            "task_meta": state.current_task.meta if state.current_task else {},
            "history": [
                {"agent": h.agent_name, "ok": h.output is not None,
                 "err": h.error, "ms": h.latency_ms}
                for h in state.history
            ],
            "artifacts": state.artifacts,
            "status": state.status,
        }

    @staticmethod
    def restore(blob: dict) -> RunState:
        st = RunState()
        st.run_id = blob["run_id"]
        st.workflow_name = blob["workflow"]
        st.step_idx = blob["step_idx"]
        if blob.get("task_payload") is not None:
            st.current_task = Task(payload=blob["task_payload"],
                                   meta=blob.get("task_meta", {}))
        st.artifacts = blob.get("artifacts", {})
        st.status = blob.get("status", "running")
        return st
