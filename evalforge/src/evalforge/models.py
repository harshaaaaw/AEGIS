"""Core models for evalforge."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class EvalCase:
    case_id: str
    input: str
    contexts: list[str] = field(default_factory=list)   # retrieved docs / transcript
    expected: str | None = None                          # exact match (rare)
    must_contain: list[str] = field(default_factory=list)
    must_not_contain: list[str] = field(default_factory=list)
    regex: str | None = None
    require_citation: bool = False                       # [n] markers vs contexts
    judge_rubric: dict | None = None                     # {"min_score": 4, "criteria": "..."}


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class CaseResult:
    case_id: str
    output: str
    checks: list[CheckResult]
    latency_ms: float = 0.0

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]


@dataclass
class GoldenSet:
    """A versioned regression suite. Bump `version` when cases change so
    score diffs always compare against a known baseline."""
    name: str
    version: str
    cases: list[EvalCase]

    @staticmethod
    def new(name: str, version: str) -> GoldenSet:
        return GoldenSet(name=name, version=version, cases=[])


@dataclass
class RunReport:
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    suite: str = ""
    suite_version: str = ""
    total: int = 0
    passed: int = 0
    recall_at_k: float | None = None      # retrieval quality, if contexts ranked
    faithfulness: float | None = None     # citation-valid rate
    started: float = field(default_factory=time.time)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


@dataclass
class ScoreDiff:
    baseline_run: str
    candidate_run: str
    pass_rate_before: float
    pass_rate_after: float
    regressions: list[str] = field(default_factory=list)   # case_ids that flipped to fail
    fixes: list[str] = field(default_factory=list)         # flipped to pass

    @property
    def delta(self) -> float:
        return self.pass_rate_after - self.pass_rate_before

    @property
    def should_block_merge(self) -> bool:
        return self.delta < -0.02 or bool(self.regressions)
