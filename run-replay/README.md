# run-replay

**Time-travel forensics for LLM agent runs. Record every step, replay it exactly, and prove nobody tampered with the log.**

When an agent does something expensive or wrong, the first question is always "why?" run-replay is the evidence layer: it records every model call, tool call, and state snapshot of an agent loop, then replays it deterministically and verifies the record was not edited after the fact. It is the spine AEGIS, CAUSALA, and SIMFORGE all build on.

## Why this is the room everyone assumes exists but rarely ships

Loggers dump JSON. run-replay makes the log verifiable: each recorded run carries a hash chain, so a single edited line is caught and the exact corrupted step is named. That is the difference between "we have logs" and "we can prove what happened."

## What it actually does

- **Recorder**: appends every step (model call, tool call, state snapshot) to a tamper-evident JSONL.
- **Replayer**: replays a recorded run and returns a `ReplayResult` with `digests_match`.
- **time_travel**: jump to any step and inspect the state at that point.
- **Tamper detection**: edit one line on disk and `verify()` names the corrupted step.

## Quickstart

```bash
pip install -e "./run-replay"

from run_replay import Recorder, Replayer, RunMeta, StepKind

rec = Recorder(state_dir="./runs", meta=RunMeta(run_id="r1", agent_name="support"))
rec.step(StepKind.MODEL_CALL, "planner", inp={"x": 1}, out={"y": 2}, state={"x": 1}, wall_ms=5)

events = rec.load_run(rec.path)[1]
res = Replayer(events).verify()
print(res.digests_match, res.steps_replayed)   # True, 1

# Tamper with the file and re-verify
# -> res.digests_match is False and diverged_at names the step
```

## Quality (measured)

| Signal | Value |
|---|---|
| Tests | 6 green (record, replay, time-travel, tamper detection) |
| Ruff | clean |
| Mypy | clean |
| Bandit | clean |

Run: `pytest run-replay/tests/ -q`

## Honest limitations

- The recorder writes JSONL; the hash chain is over the canonical step form, not the raw bytes, so cosmetic reformatting does not false-positive.
- Replay is deterministic over recorded events. Live nondeterminism is the agent's problem, not the recorder's; run-replay faithfully reproduces what was recorded.

## License

MIT.
