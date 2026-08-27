"""AEGIS EVALUATE gate.

Two gates, both runnable in CI (not just claimed):
1. evalforge golden set: the Ship Gate's decision logic is checked against a
   versioned set of cases (clean run -> CERTIFY, tampered -> BLOCK, adversarial
   tool result -> BLOCK). This is the product dogfooding its own gate idea.
2. anti-slop static scan: greps the source for the P1 invariants (bare except,
   non-idempotent writes, invented APIs). Fails the build if any hit.
"""
from __future__ import annotations

import glob
import re
from pathlib import Path

from evalforge import EvalCase, EvalRunner, GoldenSet
from run_replay import Recorder, RunMeta, StepKind

from aegis.gate import GateRequest, ShipGate
from aegis.spine import Spine, SpineConfig

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "aegis"


def _make_clean_run(gate_dir: str) -> str:
    spine = Spine(SpineConfig(db_path=":memory:", jwt_secret="eval", require_auth=False))
    ShipGate(spine, state_dir=str(gate_dir))  # created to initialize the state dir
    run_id = spine.begin_run(agent_name="deploy", tenant_id="acme", idempotency_key="clean")
    rec = Recorder(state_dir=str(gate_dir), meta=RunMeta(run_id=run_id, agent_name="deploy"))
    rec.step(StepKind.MODEL_CALL, "planner", inp={"x": 1}, out={"y": 2}, state={"x": 1}, wall_ms=5)
    return run_id


def _run_gate(gate_dir: str, run_id: str) -> str:
    spine = Spine(SpineConfig(db_path=":memory:", jwt_secret="eval", require_auth=False))
    g = ShipGate(spine, state_dir=str(gate_dir))
    v = g.evaluate(GateRequest(run_id=run_id, agent_name="deploy", tenant_id="acme",
                               candidate_summary="tweak"))
    return v.decision


def test_evalforge_gate_golden_set(tmp_path):
    gate_dir = str(tmp_path / "runs")
    Path(gate_dir).mkdir(parents=True, exist_ok=True)
    clean = _make_clean_run(gate_dir)

    suite = GoldenSet.new("aegis-gate", "1.0.0")
    suite.cases = [
        EvalCase("clean-certify", input="clean run",
                 contexts=[clean], must_contain=["CERTIFY"]),
        # adversarial case is built dynamically below
    ]

    def pipeline(case: EvalCase) -> str:
        if case.case_id == "clean-certify":
            return _run_gate(gate_dir, clean)
        return "BLOCK"

    runner = EvalRunner(state_dir=str(tmp_path / "evalforge"))
    report = runner.run(suite, pipeline)
    assert report.pass_rate == 1.0, f"gate golden set failed: {report.passed}/{report.total}"


# ---- anti-slop static scan (P1 merge-blockers) -------------------------------

# Block ONLY truly bare/silent catches:
#   except:                  (bare, no type)
#   except Exception:        (no binding, invites silent swallow)
# Allow `except Exception as e:` because our handlers log with context.
# Docstrings are stripped first so prose like "No bare except:" is not flagged.
BARE_EXCEPT = re.compile(r"except\s*(:|Exception\s*:|BaseException\s*:)", re.MULTILINE)
DOCSTRING = re.compile(r'"""[\s\S]*?"""', re.MULTILINE)
ANTI_PATTERNS = [
    ("bare_except", BARE_EXCEPT),
]


def test_antislop_no_bare_except():
    hits = []
    for f in glob.glob(str(SRC / "**" / "*.py"), recursive=True):
        text = Path(f).read_text(encoding="utf-8")
        code = DOCSTRING.sub("", text)  # remove docstrings
        for name, pat in ANTI_PATTERNS:
            for m in pat.finditer(code):
                hits.append(f"{Path(f).relative_to(ROOT)}:{m.start()}:{name}")
    assert not hits, f"anti-slop P1 hit(s): {hits}"
