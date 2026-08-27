import json

import pytest

from run_replay import (
    Recorder, RunMeta, StepKind, Replayer, sha, time_travel,
)


@pytest.fixture()
def rec(tmp_path):
    return Recorder(state_dir=tmp_path / "rr", meta=RunMeta(agent_name="support-agent", seed=42))


def _simulate_run(rec: Recorder):
    """A tiny fake agent run: model -> tool -> model, with state."""
    state = {"goal": "refund order 8123", "cart": [], "retries": 0}

    rec.step(StepKind.MODEL_CALL, "planner-v2",
             inp={"prompt": "user wants refund for order 8123"},
             out={"action": "call_tool", "tool": "lookup_order"},
             state=state, wall_ms=412.0)

    state = {**state, "cart": [{"order": 8123, "status": "delivered"}]}
    rec.step(StepKind.TOOL_CALL, "lookup_order",
             inp={"order_id": 8123},
             out={"status": "delivered", "amount_cents": 12900},
             state=state, wall_ms=87.5)

    state = {**state, "retries": 1}
    rec.step(StepKind.MODEL_CALL, "planner-v2",
             inp={"prompt": "order delivered; draft refund"},
             out={"action": "final", "refund_cents": 12900},
             state=state, wall_ms=389.0)
    return rec


# ---- recording -----------------------------------------------------------

def test_records_all_steps(rec):
    _simulate_run(rec)
    meta, events = rec.load_run(rec.path)
    assert meta["agent"] == "support-agent"
    assert len(events) == 3
    kinds = [e.kind for e in events]
    assert kinds == [StepKind.MODEL_CALL, StepKind.TOOL_CALL, StepKind.MODEL_CALL]


def test_digests_are_deterministic(rec):
    _simulate_run(rec)
    _, events = rec.load_run(rec.path)
    for ev in events:
        assert sha(ev.input_data) == ev.input_digest
        assert sha(ev.output_data) == ev.output_digest


# ---- replay verification ---------------------------------------------------

def test_verify_replays_clean(rec):
    _simulate_run(rec)
    _, events = rec.load_run(rec.path)
    res = Replayer(events).verify()
    assert res.digests_match and res.diverged_at is None
    assert res.steps_replayed == 3


def test_verify_catches_tampered_step(rec, tmp_path):
    _simulate_run(rec)
    # tamper with the stored tool output on disk
    lines = Path_text(rec.path).splitlines()
    e = json.loads(lines[2])
    e["out"]["amount_cents"] = 99999999          # someone edits history
    lines[2] = json.dumps(e, separators=(",", ":"))
    (tmp_path and open(rec.path, "w", encoding="utf-8")).write("\n".join(lines) + "\n")

    _, events = rec.load_run(rec.path)
    res = Replayer(events).verify()
    assert not res.digests_match and res.diverged_at == 1   # caught at the tool step


# ---- counterfactual divergence ----------------------------------------------

def test_divergence_pinpoints_the_what_if(rec):
    _simulate_run(rec)
    _, events = rec.load_run(rec.path)
    alt = {"status": "lost_in_transit", "amount_cents": 12900}   # different tool answer
    res = Replayer(events).divergence(substitute_at_step=1, new_output=alt)
    assert res.diverged_at == 1
    assert any("DIVERGE" in line for line in res.trajectory)


def test_time_travel_shows_what_agent_knew(rec):
    _simulate_run(rec)
    _, events = rec.load_run(rec.path)
    world = time_travel(events, to_step=1)
    assert world["step"] == 1
    assert world["observation"]["status"] == "delivered"
    assert len(world["agent_knew"]) == 2         # planner out + tool result


# ---- helpers ------------------------------------------------------------------

def Path_text(p):
    with open(p, encoding="utf-8") as f:
        return f.read()
