"""Core types for run-replay: forensic recording of agent runs."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class StepKind(str, Enum):
    MODEL_CALL = "model_call"
    TOOL_CALL = "tool_call"
    OBSERVATION = "observation"     # environment change the agent perceived
    STATE = "state"                 # full state snapshot marker


@dataclass
class StepEvent:
    idx: int                        # position in the run
    kind: StepKind
    name: str                       # model/tool name
    input_digest: str               # sha256 of canonical input JSON
    output_digest: str              # sha256 of canonical output JSON
    input_data: dict | None         # stored inline (small) or None if large
    output_data: dict | None
    state_hash: str                 # hash of full agent state after this step
    wall_ms: float
    ts: float = field(default_factory=time.time)

    def digest(self) -> str:
        payload = json.dumps({
            "idx": self.idx, "kind": self.kind.value, "name": self.name,
            "in": self.input_digest, "out": self.output_digest,
            "state": self.state_hash,
        }, sort_keys=True).encode()
        return hashlib.sha256(payload).hexdigest()[:16]


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha(obj) -> str:
    return hashlib.sha256(canon(obj).encode()).hexdigest()


@dataclass
class RunMeta:
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_name: str = "agent"
    started: float = field(default_factory=time.time)
    seed: int | None = None         # captured RNG seed for determinism
