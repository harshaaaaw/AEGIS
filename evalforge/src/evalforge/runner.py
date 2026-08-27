"""The runner: execute a golden set against any callable, diff runs, gate merges."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from pathlib import Path

from .checks import run_checks
from .models import CaseResult, EvalCase, GoldenSet, RunReport, ScoreDiff


class EvalRunner:
    def __init__(self, state_dir: str | os.PathLike = ".evalforge"):
        self.state = Path(state_dir)
        self.state.mkdir(parents=True, exist_ok=True)

    # ---- execution ------------------------------------------------------

    def run(self, suite: GoldenSet,
            pipeline: Callable[[EvalCase], str],
            k: int | None = None) -> RunReport:
        """pipeline(case) -> answer string. k = retrieval cutoff for recall@k."""
        report = RunReport(suite=suite.name, suite_version=suite.version)
        cit_total = cit_ok = 0
        rel_total = rel_hit = 0

        for case in suite.cases:
            t0 = time.perf_counter()
            output = pipeline(case)
            ms = (time.perf_counter() - t0) * 1000

            checks = run_checks(case, output)
            cr = CaseResult(case.case_id, output, checks, ms)
            report.total += 1
            report.passed += int(cr.passed)

            if case.require_citation:
                cit_total += 1
                if all(c.passed for c in checks if c.name == "citations_valid"):
                    cit_ok += 1
            # recall@k proxy: did the cited source rank inside top-k contexts?
            if case.require_citation and case.contexts and k:
                marks = [int(m) for m in
                         __import__("re").findall(r"\[(\d+)\]", output)]
                rel_total += 1
                if marks and all(1 <= m <= k for m in marks):
                    rel_hit += 1

            self._persist(report.run_id, cr)

        if cit_total:
            report.faithfulness = cit_ok / cit_total
        if rel_total:
            report.recall_at_k = rel_hit / rel_total
        return report

    def _persist(self, run_id: str, cr: CaseResult):
        with open(self.state / f"run-{run_id}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "case": cr.case_id, "passed": cr.passed, "ms": round(cr.latency_ms, 1),
                "failed": [c.name for c in cr.failures()],
            }) + "\n")

    # ---- regression gating -------------------------------------------------

    @staticmethod
    def diff(baseline: RunReport, candidate: RunReport,
             baseline_cases: dict[str, bool], candidate_cases: dict[str, bool]) -> ScoreDiff:
        d = ScoreDiff(
            baseline_run=baseline.run_id, candidate_run=candidate.run_id,
            pass_rate_before=baseline.pass_rate, pass_rate_after=candidate.pass_rate,
        )
        for case_id, ok_now in candidate_cases.items():
            was = baseline_cases.get(case_id)
            if was is True and not ok_now:
                d.regressions.append(case_id)
            elif was is False and ok_now:
                d.fixes.append(case_id)
        return d

    @staticmethod
    def verdict(diff: ScoreDiff) -> str:
        if diff.should_block_merge:
            return "BLOCK"
        return "PASS" if diff.delta >= 0 else "WARN"
