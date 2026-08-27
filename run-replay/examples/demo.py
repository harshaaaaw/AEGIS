"""Incident walkthrough: a refund agent took a weird action at 3am.
Reconstruct what happened, prove the logs weren't touched, find the
step where everything diverged.

Run: python examples/demo.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from run_replay import (
    Recorder, RunMeta, StepKind, Replayer, time_travel,
)

print("=" * 64)
print("INCIDENT: support agent refunded $12,900 instead of $129")
print("=" * 64)

rec = Recorder(state_dir=".rr-demo", meta=RunMeta(agent_name="support-agent", seed=7))
state = {"goal": "refund order 8123", "amount_cents": None}

rec.step(StepKind.MODEL_CALL, "planner-v2",
         inp={"prompt": "Customer complains order never arrived. Handle it."},
         out={"action": "call_tool", "tool": "lookup_order", "order_id": 8123},
         state=state, wall_ms=401.0)

state = {**state, "order_status": "delivered"}
rec.step(StepKind.TOOL_CALL, "lookup_order",
         inp={"order_id": 8123},
         out={"status": "delivered_in_error", "duplicate_of": None,
              "amount_cents": 12900},
         state=state, wall_ms=92.0)

state = {**state, "amount_cents": 12900}
rec.step(StepKind.MODEL_CALL, "planner-v2",
         inp={"prompt": "Order marked delivered_in_error. Issue refund."},
         out={"action": "final", "refund_cents": 12900},
         state=state, wall_ms=377.0)

_, events = rec.load_run(rec.path)

print("\n[1] VERIFY - were the logs tampered with?")
res = Replayer(events).verify()
print(f"    digests_match={res.digests_match} over {res.steps_replayed} steps")

print("\n[2] TIME TRAVEL - what did the agent know when it chose $12,900?")
world = time_travel(events, to_step=1)
print(f"    observation at step 1: {world['observation']}")
print(f"    state hash           : {world['state_hash'][:16]}...")

print("\n[3] DIVERGENCE - what if lookup_order had said 'delivered'?")
fixed = {"status": "delivered", "duplicate_of": None, "amount_cents": 12900}
dres = Replayer(events).divergence(substitute_at_step=1, new_output=fixed)
print(f"    trajectories split at step {dres.diverged_at}")
for line in dres.trajectory[-1:]:
    print(f"    {line}")

print("\nVERDICT: tool returned 'delivered_in_error' with no duplicate check;")
print("the planner followed orders. Fix belongs in the tool contract.")
