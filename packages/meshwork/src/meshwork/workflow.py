"""Workflow engine: typed steps, retries, human gates, checkpoint/resume.

A workflow is a list of steps. Each step is:
    (agent_name, callable(task)->dict|None, policy)

None return or raised exception = step failed; the policy decides retry
vs skip vs halt. After every step the engine checkpoints, so a crash at
step 14 of 30 resumes at step 14 with artifacts intact - the property
Matterhaul's JD calls 'plan/execute loops with checkpointing and
graceful degradation when a step fails'.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from .models import Checkpoint, RunState, StepResult, Task


@dataclass
class RetryPolicy:
    max_attempts: int = 2          # total tries per step
    backoff_s: float = 0.05        # tests stay fast
    on_exhaust: str = "halt"       # halt | skip | human


@dataclass
class Step:
    name: str
    agent: Callable[[Task, RunState], dict | None]
    policy: RetryPolicy = field(default_factory=RetryPolicy)
    requires_human_signoff: bool = False


class Workflow:
    def __init__(self, name: str):
        self.name = name
        self.steps: list[Step] = []
        self._pending_gate = False

    def add(self, name: str, agent: Callable[[Task, RunState], dict | None],
            **policy_kwargs) -> Workflow:
        if any(s.name == name for s in self.steps):
            raise ValueError(f"duplicate step name {name!r}; "
                             "names key checkpoint resume")
        step = Step(name, agent, RetryPolicy(**policy_kwargs),
                    requires_human_signoff=self._pending_gate)
        self._pending_gate = False
        self.steps.append(step)
        return self

    def gate(self) -> Workflow:
        """Arm a human-approval gate for the NEXT step added:
        wf.add('propose', f).gate().add('execute', g) gates 'execute'."""
        self._pending_gate = True
        return self

    # ---- execution -------------------------------------------------------

    def run(self, task: Task, *, approvals: Callable[[RunState, str], bool] | None = None,
            state: RunState | None = None,
            checkpoint_sink: Callable[[dict], None] | None = None) -> RunState:
        """Run (or resume) the workflow.

        Resume semantics are NAME-based, not positional: a step runs iff
        its name is absent from state.history. This keeps checkpoints
        valid across deploys that insert/reorder steps - the failure mode
        of naive index-based resume.
        """
        st = state or RunState(workflow_name=self.name)
        st.workflow_name = self.name
        if st.current_task is None:
            st.current_task = task

        done_names = {h.agent_name for h in st.history}

        for idx, step in enumerate(self.steps):
            if step.name in done_names:
                st.step_idx = idx + 1
                continue

            if step.requires_human_signoff and not (approvals and approvals(st, step.name)):
                st.status = "awaiting_human"
                st.step_idx = idx
                self._sink(checkpoint_sink, st)
                return st                        # resumable exactly here

            result = self._attempt(step, st)
            st.history.append(result)

            if result.output is None:
                st.status = "failed"
                st.step_idx = idx
                self._sink(checkpoint_sink, st)
                return st                            # graceful degradation: stop clean

            st.artifacts[step.name] = result.output
            st.current_task.payload = {**(st.current_task.payload),
                                       **(result.output or {})}
            st.step_idx = idx + 1
            self._sink(checkpoint_sink, st)

        st.status = "done"
        st.finished = time.time()
        self._sink(checkpoint_sink, st)
        return st

    # ---- internals --------------------------------------------------------

    def _attempt(self, step: Step, st: RunState) -> StepResult:
        attempts, last_err = 0, None
        while attempts < step.policy.max_attempts:
            attempts += 1
            t0 = time.perf_counter()
            try:
                out = step.agent(st.current_task, st)   # type: ignore[arg-type]
                ms = (time.perf_counter() - t0) * 1000
                if out is not None:
                    return StepResult(step.name, out, latency_ms=ms)
                last_err = "agent returned None"
            except Exception as e:                       # noqa: BLE001 - engine boundary
                last_err = f"{type(e).__name__}: {e}"
            if attempts < step.policy.max_attempts:
                time.sleep(step.policy.backoff_s)
        return StepResult(step.name, None, error=last_err or "exhausted")

    def _sink(self, sink, st: RunState):
        if sink is not None:
            sink(Checkpoint.save(st))
