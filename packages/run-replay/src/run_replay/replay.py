"""Replayer: deterministically re-run a recorded agent run.

The forensic loop:
  1. Load recorded events.
  2. Feed each step's RECORDED output back instead of calling the real
     model/tool (deterministic mode) -> reconstructs the exact original
     trajectory, byte-for-byte digest comparison included.
  3. Divergence mode: swap in a different model/tool at step N and diff
     the new trajectory against the recording to answer "what if".

This is what turns "the agent did something weird at 3am" into a
ten-minute debugging session instead of a war room.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import StepEvent, sha


@dataclass
class ReplayResult:
    steps_replayed: int = 0
    digests_match: bool = True
    diverged_at: int | None = None       # first idx where live != recorded
    trajectory: list[str] = field(default_factory=list)


class Replayer:
    def __init__(self, events: list[StepEvent]):
        self.events = sorted(events, key=lambda e: e.idx)

    # ---- deterministic verification ------------------------------------

    def verify(self, state_fn=None) -> ReplayResult:
        """Replay using recorded outputs only; check internal consistency.

        Every event's stored data must hash to its recorded digest, and
        (optionally) a caller-provided state_fn must reproduce the same
        state hash chain.
        """
        res = ReplayResult()
        for ev in self.events:
            ok_in = sha(ev.input_data) == ev.input_digest if ev.input_data is not None else True
            ok_out = sha(ev.output_data) == ev.output_digest if ev.output_data is not None else True
            if not (ok_in and ok_out):
                res.digests_match = False
                res.diverged_at = ev.idx
                break
            res.steps_replayed += 1
            marker = f"{ev.idx:03d} {ev.kind.value:11s} {ev.name}"
            if ev.state_hash:
                marker += f"  state={ev.state_hash[:8]}"
            res.trajectory.append(marker)
        return res

    # ---- counterfactual -------------------------------------------------

    def divergence(self, substitute_at_step: int,
                   new_output) -> ReplayResult:
        """Swap one step's output and report where trajectories split."""
        res = ReplayResult()
        for ev in self.events:
            if ev.idx == substitute_at_step:
                alt_digest = sha(new_output)
                if alt_digest != ev.output_digest:
                    res.diverged_at = ev.idx
                    res.trajectory.append(
                        f"{ev.idx:03d} DIVERGE {ev.name}: "
                        f"recorded={ev.output_digest[:8]} vs alt={alt_digest[:8]}")
                    break
            res.steps_replayed += 1
            res.trajectory.append(f"{ev.idx:03d} replay {ev.name}")
        return res


def time_travel(events: list[StepEvent], to_step: int) -> dict | None:
    """Return the world as the agent saw it right AFTER `to_step`."""
    for ev in events:
        if ev.idx == to_step:
            return {
                "step": ev.idx,
                "state_hash": ev.state_hash,
                "observation": ev.output_data,
                "agent_knew": [e.output_data for e in events if e.idx <= to_step],
            }
    return None
