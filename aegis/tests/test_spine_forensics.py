"""Phase 0, Tracer 1: Audit Spine record + forensic verify (idempotent, tamper-evident)."""
from __future__ import annotations

from pathlib import Path

from run_replay import Recorder, Replayer, RunMeta, StepKind, time_travel

from aegis.spine import Spine


def test_spine_records_step_and_verifies_intact(spine: Spine, tmp_state: Path):
    """A recorded run must verify digests_match=True and replay bit-for-bit."""
    run_id = spine.begin_run(agent_name="support", tenant_id="acme",
                             idempotency_key="evt-refund-8123")
    rec = Recorder(state_dir=str(tmp_state), meta=RunMeta(run_id=run_id, agent_name="support"))
    rec.step(StepKind.MODEL_CALL, "planner", inp={"goal": "refund 8123"},
             out={"action": "call_tool"}, state={"goal": "refund 8123"}, wall_ms=12.0)
    rec.step(StepKind.TOOL_CALL, "refund", inp={"order": 8123},
             out={"status": "ok"}, state={"refunded": True}, wall_ms=40.0)

    _meta, events = rec.load_run(rec.path)
    res = Replayer(events).verify()
    assert res.digests_match is True, "history was tampered or corrupted"
    assert res.steps_replayed == 2

    # time_travel answers 'what did the agent know right after step 0?'
    world = time_travel(events, to_step=0)
    assert world is not None
    # agent_knew collects the *output* of every step up to and including to_step.
    assert world["agent_knew"][0] == {"action": "call_tool"}
    assert world["observation"] == {"action": "call_tool"}


def test_spine_idempotent_begin_run(spine: Spine):
    """Replaying the same idempotency_key returns the SAME run_id, not a new one."""
    r1 = spine.begin_run(agent_name="support", tenant_id="acme", idempotency_key="ik-1")
    r2 = spine.begin_run(agent_name="support", tenant_id="acme", idempotency_key="ik-1")
    assert r1 == r2, "duplicate idempotency key must map to the same run"


def test_spine_detects_tampered_run(spine: Spine, tmp_state: Path):
    """If an event's stored data is edited, verify() must name the corrupted step."""
    run_id = spine.begin_run(agent_name="support", tenant_id="acme", idempotency_key="tamper-1")
    rec = Recorder(state_dir=str(tmp_state), meta=RunMeta(run_id=run_id, agent_name="support"))
    rec.step(StepKind.MODEL_CALL, "planner", inp={"x": 1}, out={"y": 2},
             state={"x": 1}, wall_ms=5.0)

    # Simulate an attacker editing the JSONL on disk (altering output_data).
    lines = Path(rec.path).read_text(encoding="utf-8").splitlines()
    import json
    edited = json.loads(lines[1])
    edited["out"] = {"y": 999}  # tamper
    lines[1] = json.dumps(edited)
    Path(rec.path).write_text("\n".join(lines) + "\n", encoding="utf-8")

    _, events = rec.load_run(rec.path)
    res = Replayer(events).verify()
    assert res.digests_match is False
    assert res.diverged_at == 0, "verify must pinpoint the tampered step"
