"""Deterministic checks + judge integration."""

from __future__ import annotations

import re

from .models import CheckResult, EvalCase


def _citation_ok(output: str, contexts: list[str]) -> bool:
    """Faithfulness proxy: every [n] marker must point at a real context,
    and at least one citation must exist."""
    marks = re.findall(r"\[(\d+)\]", output)
    if not marks or not contexts:
        return False
    return all(1 <= int(m) <= len(contexts) for m in set(marks))


def _strip_citations(s: str) -> str:
    return re.sub(r"\s*\[\d+\]", "", s)


def run_checks(case: EvalCase, output: str) -> list[CheckResult]:
    checks: list[CheckResult] = []

    if case.expected is not None:
        # exact_match compares CONTENT; [n] citation markers are a separate
        # concern checked by citations_valid.
        ok = (_strip_citations(output).strip().lower()
              == case.expected.strip().lower())
        checks.append(CheckResult("exact_match", ok,
                                  f"expected {case.expected!r}"))

    for frag in case.must_contain:
        checks.append(CheckResult(f"contains:{frag[:24]}",
                                  frag.lower() in output.lower(),
                                  f"missing {frag!r}" if frag.lower() not in output.lower() else ""))

    for frag in case.must_not_contain:
        bad = frag.lower() in output.lower()
        checks.append(CheckResult(f"not_contains:{frag[:24]}", not bad,
                                  "forbidden string present" if bad else ""))

    if case.regex:
        checks.append(CheckResult("regex", re.search(case.regex, output) is not None,
                                  f"/{case.regex}/"))

    if case.require_citation:
        ok = _citation_ok(output, case.contexts)
        checks.append(CheckResult("citations_valid", ok,
                                  "answer cites sources as [n]" if ok else
                                  "missing or invalid [n] citations"))

    return checks


def attach_judge_check(case: EvalCase, result_case_output: str,
                       judge, human_labels: dict[str, int] | None = None):
    """Score with the judge; mark check uncalibrated when no labels given."""
    score, reason = judge.score(case, result_case_output)
    min_score = (case.judge_rubric or {}).get("min_score", 3)
    passed = score >= min_score
    calib = judge.calibrated()
    detail = f"judge={score}>={min_score}:{reason}"
    if not calib:
        detail += " [UNCALIBRATED]"
    return CheckResult("llm_judge", passed, detail)


def calibration_agreement(judge, labeled_cases, human_labels: dict[str, int],
                          min_score_map: dict[str, int]) -> float:
    """Fraction of cases where judge verdict matches human pass/fail."""
    agree = total = 0
    for case in labeled_cases:
        score, _ = judge.score(case, case.output if hasattr(case, "output") else "")
        human_pass = human_labels.get(case.case_id, 0) >= min_score_map.get(case.case_id, 3)
        judge_pass = score >= min_score_map.get(case.case_id, 3)
        agree += int(human_pass == judge_pass)
        total += 1
    return agree / total if total else 0.0
