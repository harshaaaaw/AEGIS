"""evalforge: golden-set evals with CI gating for LLM pipelines."""

from .models import CheckResult, EvalCase, GoldenSet, RunReport, ScoreDiff
from .runner import EvalRunner

__version__ = "1.0.0"

__all__ = [
    "CheckResult", "EvalCase", "EvalRunner", "GoldenSet",
    "RunReport", "ScoreDiff",
]
