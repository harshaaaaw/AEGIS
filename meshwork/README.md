# meshwork

**Multi-agent workflows that survive a crash at step 14 of 30, and pause for a human exactly where they should.**

Orchestration frameworks love the happy path. meshwork is built for the part nobody demos: a step throws, the run dies, and you need to resume from step 14 with every artifact intact, or stop and wait for a human sign-off before a refund goes out. It checkpoints after every step, so failure is a resume point, not a restart.

## Why this is the room frameworks skip

LangGraph and friends give you a graph. They do not give you crash-resume with intact state, or a human gate that holds the run resumable exactly at the blocked step. meshwork does both, with a typed step model and a generator-critic loop you can actually read.

## What it actually does

- **Workflow**: a list of named steps, each a callable `(task, state) -> dict | None`.
- **RetryPolicy**: per-step attempts, backoff, and `halt | skip | human` on exhaustion.
- **Human gates**: a step can require sign-off; the run parks at `awaiting_human` and resumes from there.
- **Checkpoint / RunState**: every step persists, so a crash resumes at the right index.
- **Generator-critic loop**: a critic can reject weak output and force a retry, not just pass/fail.

## Quickstart

```bash
pip install -e "./meshwork"

from meshwork import Workflow, Task

def planner(task, state):
    return {"plan": ["draft", "review", "send"]}

def drafter(task, state):
    return {"draft": f"Dear {task.payload['customer']}, here is your reply."}

def critic(task, state):
    draft = task.payload.get("draft", "")
    return {"approved": len(draft) >= 20, "reason": "too short" if len(draft) < 20 else ""}

wf = Workflow("support-reply").add("plan", planner).add("draft", drafter).add("critique", critic)
st = wf.run(Task(payload={"customer": "Acme"}))
print(st.status, st.history)
```

## Quality (measured)

| Signal | Value |
|---|---|
| Tests | 6 green (generator-critic, resume, human gate, exhaustion) |
| Ruff | clean |
| Mypy | clean |
| Bandit | clean |

Run: `pytest meshwork/tests/ -q`

## Honest limitations

- The checkpoint sink is pluggable; the demo uses an in-memory sink so tests stay fast. Point it at your store for production resume.
- Concurrency is single-threaded per run; parallel fan-out is a host concern, not handled inside the engine.

## License

MIT.
