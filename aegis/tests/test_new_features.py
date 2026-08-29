"""Tests for tui, any-agent, skills, quickstart."""
from typer.testing import CliRunner
from aegis.cli import app
import pathlib, tempfile, os
runner = CliRunner()
def test_quickstart_creates_and_certifies(tmp_path):
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        # ensure no run.jsonl
        if (tmp_path / "run.jsonl").exists():
            (tmp_path / "run.jsonl").unlink()
        r = runner.invoke(app, ["quickstart"])
        assert r.exit_code == 0, r.output
        assert "CERTIFY" in r.output
        assert (tmp_path / "run.jsonl").exists()
    finally:
        os.chdir(cwd)
def test_agent_generic():
    r = runner.invoke(app, ["agent", "generic", "--cmd", "echo hi", "hello"])
    assert r.exit_code == 0, r.output
    assert "CERTIFY" in r.output or "generic" in r.output
def test_skill_flow():
    r = runner.invoke(app, ["skill", "list"])
    assert r.exit_code == 0, r.output
    assert "aegis-watch" in r.output
    r2 = runner.invoke(app, ["skill", "verify", "aegis-watch"])
    assert r2.exit_code == 0, r2.output
    assert "grounded" in r2.output.lower()
def test_watch_help():
    r = runner.invoke(app, ["watch", "--help"])
    assert r.exit_code == 0, r.output
    assert "flow" in r.output.lower()
def test_tui_import():
    from aegis.tui.app import AegisTUI
    assert AegisTUI is not None
