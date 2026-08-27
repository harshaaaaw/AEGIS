"""Recorder: wrap an agent loop, persist every step as replayable events."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from .models import RunMeta, StepEvent, StepKind, sha


class Recorder:
    """Append one JSONL line per step into runs/<run_id>.jsonl."""

    def __init__(self, state_dir: str | os.PathLike, meta: RunMeta | None = None):
        self.meta = meta or RunMeta()
        self.dir = Path(state_dir) / "runs"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / f"{self.meta.run_id}.jsonl"
        self._lock = threading.Lock()
        self._idx = 0
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"meta": {
                "run_id": self.meta.run_id, "agent": self.meta.agent_name,
                "started": self.meta.started, "seed": self.meta.seed,
            }}) + "\n")

    def _log(self, ev: StepEvent):
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "idx": ev.idx, "kind": ev.kind.value, "name": ev.name,
                "in_d": ev.input_digest, "out_d": ev.output_digest,
                "in": ev.input_data, "out": ev.output_data,
                "state": ev.state_hash, "ms": round(ev.wall_ms, 2),
            }, separators=(",", ":")) + "\n")

    def step(self, kind: StepKind, name: str,
             inp=None, out=None, state=None, wall_ms: float = 0.0) -> StepEvent:
        ev = StepEvent(
            idx=self._idx, kind=kind, name=name,
            input_digest=sha(inp), output_digest=sha(out),
            input_data=inp, output_data=out,
            state_hash=sha(state) if state is not None else "",
            wall_ms=wall_ms,
        )
        self._log(ev)
        self._idx += 1
        return ev

    def load_run(self, path: str | os.PathLike) -> tuple[dict, list[StepEvent]]:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        meta = json.loads(lines[0])["meta"]
        events = []
        for raw in lines[1:]:
            e = json.loads(raw)
            events.append(StepEvent(
                idx=e["idx"], kind=StepKind(e["kind"]), name=e["name"],
                input_digest=e["in_d"], output_digest=e["out_d"],
                input_data=e.get("in"), output_data=e.get("out"),
                state_hash=e.get("state", ""), wall_ms=e.get("ms", 0.0),
            ))
        return meta, events
