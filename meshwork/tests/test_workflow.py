"""Generator-critic loops, resume-after-crash, human gates, exhaustion."""

import pytest

from meshwork import Checkpoint, RunState, Task, Workflow


# ---- happy path: generator -> critic -> act -------------------------------

def test_generator_critic_pipeline_runs():
    calls = []

    def planner(task, state):
        calls.append("plan")
        return {"plan": ["draft", "review", "send"]}

    def drafter(task, state):
        calls.append("draft")
        return {"draft": f"Dear {task.payload['customer']}, here is the full reply you asked for."}

    def critic(task, state):
        calls.append("critique")
        # generator-critic loop: reject weak drafts
        draft = task.payload.get("draft", "")
        if len(draft) < 20:
            return {"approved": False, "reason": "too short"}
        return {"approved": True}

    wf = Workflow("support-reply").add("plan", planner).add("draft", drafter).add("critique", critic)
    st = wf.run(Task(payload={"customer": "Acme"}))

    assert st.status == "done"
    assert st.artifacts["critique"]["approved"] is True
    assert calls == ["plan", "draft", "critique"]


# ---- retry & graceful degradation -------------------------------------------

def test_flaky_agent_retries_then_succeeds():
    attempts = {"n": 0}

    def flaky(task, state):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise RuntimeError("transient API blip")
        return {"ok": True}

    wf = Workflow("flaky").add("call_api", flaky, max_attempts=3, backoff_s=0.001)
    st = wf.run(Task(payload={}))
    assert st.status == "done" and attempts["n"] == 2


def test_step_exhaustion_halts_with_error_attribution():
    def broken(task, state):
        raise ValueError("bad input shape")

    wf = Workflow("broken").add("explode", broken, max_attempts=2, backoff_s=0.001).add("never", broken)
    st = wf.run(Task(payload={}))

    assert st.status == "failed"
    assert "ValueError: bad input shape" in st.history[-1].error


# ---- checkpoint / crash resume --------------------------------------------------

def test_crash_at_step_14_resume_property(tmp_path):
    """The Matterhaul JD property: checkpointing so a mid-run crash resumes
    exactly where it stopped."""
    sink = []
    executed = []

    def step_a(task, state):
        executed.append("a"); return {"a_done": True}

    def step_b_crashes_midway(task, state):
        executed.append("b"); return {"b_done": True}

    wf = Workflow("long").add("a", step_a).add("b", step_b_crashes_midway)
    st = wf.run(Task(payload={"x": 1}), checkpoint_sink=sink.append)
    assert st.status == "done"

    # simulate a crash after 'b': restore from the last checkpoint at step_idx=2
    last = sink[-1]
    restored = Checkpoint.restore(last)

    def step_c(task, state):
        executed.append("c"); return {"c_done": True}

    wf2 = Workflow("long").add("c", step_c)
    st2 = wf2.run(None, state=restored)          # type: ignore[arg-type]

    assert [h.agent_name for h in st2.history] == ["c"]
    assert executed.count("b") == 1              # b never re-ran


def test_checkpoint_roundtrip_preserves_state():
    st = RunState(workflow_name="w")
    st.current_task = Task(payload={"k": "v"})
    st.artifacts = {"step1": {"answer": 42}}
    blob = Checkpoint.save(st)
    st2 = Checkpoint.restore(blob)
    assert st2.artifacts == st.artifacts and st2.run_id == st.run_id


# ---- human gate -------------------------------------------------------------------

def test_human_gate_pauses_and_resumes():
    asked = []

    def propose_refund(task, state):
        return {"refund_cents": 12900}

    def execute_refund(task, state):
        return {"executed": True}

    def approval_cb(state, step_name):
        asked.append(step_name)
        return len(asked) > 1                    # deny first ask, approve retry

    wf = (Workflow("refund")
          .add("propose", propose_refund).gate()
          .add("execute", execute_refund))

    checkpoints = []
    st = wf.run(Task(payload={"order": 8123}),
                approvals=approval_cb,
                checkpoint_sink=checkpoints.append)
    assert st.status == "awaiting_human" and asked == ["execute"]

    resumed = Checkpoint.restore(checkpoints[-1])
    st2 = wf.run(None, approvals=approval_cb, state=resumed,   # type: ignore[arg-type]
                 checkpoint_sink=checkpoints.append)
    assert st2.status == "done"
