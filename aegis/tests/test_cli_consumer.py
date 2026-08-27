"""Consumer-journey tests for the AEGIS CLI (closes 67% CLI coverage gap)."""
from __future__ import annotations

from typer.testing import CliRunner

from aegis.cli import app

runner = CliRunner()


def test_cli_certify_then_verify(tmp_path):
    run = tmp_path / "run.jsonl"
    run.write_text('{"idx":0,"kind":"MODEL_CALL","name":"planner","in":{"x":1},'
                   '"out":{"y":2},"state":{"x":1},"ms":5}\n')
    r = runner.invoke(app, ["certify", str(run)])
    assert r.exit_code == 0, r.output
    assert "CERTIFY" in r.output
    vid = r.output.split("aegis verify ")[-1].strip()
    v = runner.invoke(app, ["verify", vid])
    assert v.exit_code == 0, v.output
    assert "valid" in v.output.lower() or "signature" in v.output.lower()


def test_cli_ssrf_blocks_metadata(tmp_path):
    r = runner.invoke(app, ["ssrf", "http://169.254.169.254/latest"])
    assert r.exit_code == 0
    assert '"safe": false' in r.output


def test_cli_ssrf_allows_public(tmp_path):
    r = runner.invoke(app, ["ssrf", "https://example.com"])
    assert r.exit_code == 0
    assert '"safe": true' in r.output


def test_cli_posture_runs(tmp_path):
    r = runner.invoke(app, ["posture", "--tenant", "acme"])
    assert r.exit_code == 0
    assert "trust_tiers" in r.output  # the whole-plane view renders


def test_cli_drift_detects_change(tmp_path):
    base = tmp_path / "base.jsonl"
    live = tmp_path / "live.jsonl"
    base.write_text('{"idx":0,"kind":"MODEL_CALL","name":"p","in":{"x":1},'
                    '"out":{"y":2},"state":{"x":1},"ms":5}\n')
    live.write_text('{"idx":0,"kind":"MODEL_CALL","name":"p","in":{"x":1},'
                    '"out":{"y":999},"state":{"x":1},"ms":5}\n')
    r = runner.invoke(app, ["drift", "run-1", str(base), str(live)])
    assert r.exit_code == 0, r.output
    assert "drifted" in r.output.lower()
