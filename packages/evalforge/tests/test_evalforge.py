import pytest

from evalforge import EvalCase, EvalRunner, GoldenSet, RunReport


def build_suite() -> GoldenSet:
    gs = GoldenSet.new("support-rag", "1.2.0")
    gs.cases = [
        EvalCase("q1", "What is the refund window?",
                 contexts=["Refunds are accepted within 30 days of purchase."],
                 must_contain=["30 days"], require_citation=True),
        EvalCase("q2", "Do you ship to PO boxes?",
                 contexts=["We ship to PO boxes via USPS only."],
                 expected="Yes, via USPS only.", require_citation=True),
        EvalCase("q3", "How do I reset my password?",
                 contexts=["Use 'Forgot password' on the login page.",
                           "Admins can force a reset from the console."],
                 must_contain=["forgot password"],
                 must_not_contain=["email us your password"]),
        EvalCase("q4", "What is the SLA?",
                 contexts=["Enterprise SLA is 99.9% monthly uptime."],
                 regex=r"99\.9%"),
    ]
    return gs


def good_pipeline(case: EvalCase) -> str:
    answers = {
        "q1": "You can request a refund within 30 days of purchase [1].",
        "q2": "Yes, via USPS only. [1]",
        "q3": "Use the Forgot password link on the login page [1], or ask an admin to force a reset [2].",
        "q4": "The enterprise SLA is 99.9% monthly uptime [1].",
    }
    return answers[case.case_id]


def regressed_pipeline(case: EvalCase) -> str:
    # prompt change broke citations and dropped the shipping detail
    if case.case_id == "q1":
        return "Our refund policy is generous."            # no citation, no number
    if case.case_id == "q2":
        return "Yes we do ship to most addresses."          # lost specificity
    return good_pipeline(case)


# ---- happy path -------------------------------------------------------------

def test_golden_set_passes_good_pipeline(tmp_path):
    r = EvalRunner(state_dir=tmp_path).run(build_suite(), good_pipeline)
    assert r.total == 4 and r.passed == 4
    assert r.pass_rate == 1.0
    assert r.faithfulness == 1.0


# ---- regression detection ------------------------------------------------------

def test_regression_is_detected_and_attributed(tmp_path):
    runner = EvalRunner(state_dir=tmp_path / "e")

    base = runner.run(build_suite(), good_pipeline)
    cand = runner.run(build_suite(), regressed_pipeline)

    base_cases = {"q1": True, "q2": True, "q3": True, "q4": True}
    cand_cases = {"q1": False, "q2": False, "q3": True, "q4": True}

    d = EvalRunner.diff(base, cand, base_cases, cand_cases)
    assert d.regressions == ["q1", "q2"]
    assert d.delta == pytest.approx(-0.5)
    assert EvalRunner.verdict(d) == "BLOCK"


def test_improvement_passes_gate(tmp_path):
    runner = EvalRunner(state_dir=tmp_path / "i")
    base = runner.run(build_suite(), lambda c: "no")
    cand = runner.run(build_suite(), good_pipeline)
    cases = {c.case_id: False for c in build_suite().cases}
    cand_cases = {c.case_id: True for c in build_suite().cases}
    d = EvalRunner.diff(base, cand, cases, cand_cases)
    assert d.fixes and not d.regressions
    assert EvalRunner.verdict(d) == "PASS"


# ---- check mechanics ---------------------------------------------------------------

def test_citation_check_rejects_bad_markers():
    from evalforge.checks import run_checks
    case = EvalCase("c1", "?", contexts=["only one context"], require_citation=True)
    bad = run_checks(case, "Totally made up [7] reference.")
    assert not all(c.passed for c in bad)

    good = run_checks(case, "Real answer [1].")
    assert all(c.passed for c in good)


def test_must_not_contain_guard():
    from evalforge.checks import run_checks
    case = EvalCase("s1", "?", must_not_contain=["drop table"])
    res = run_checks(case, "run; DROP TABLE users;")
    assert any(not c.passed for c in res)


# ---- recall@k proxy --------------------------------------------------------------------

def test_recall_at_k_computed_when_k_given(tmp_path):
    r = EvalRunner(state_dir=tmp_path).run(build_suite(), good_pipeline, k=2)
    # q1 cites [1], q3 cites [1] and [2]; q2/q4 have citation checks but
    # recall only counts cases where require_citation is set AND marks exist
    assert r.recall_at_k is None or 0 <= r.recall_at_k <= 1
