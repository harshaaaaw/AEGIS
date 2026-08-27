"""Phase 0/1, Tracer 3: HTTP API surface (async, authenticated, SSRF-safe).

Endpoints:
  POST /api/v1/runs          -> begin a run (idempotent via idempotency_key)
  POST /api/v1/gate/evaluate -> run the Ship Gate on a run, return signed verdict
  GET  /api/v1/verdicts/{id} -> fetch + cryptographically verify a stored verdict
Anti-slop: external links are SSRF-validated before any fetch; authN is a real
JWT check (OIDC-style), not a stub that trusts the client.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from aegis.security import is_ssrf_safe, make_token


def test_begin_run_idempotent(client: TestClient):
    tok = make_token("acme", "deploy-agent", secret="0" * 32)
    h = {"Authorization": f"Bearer {tok}"}
    body = {"agent_name": "deploy", "tenant_id": "acme", "idempotency_key": "api-1"}
    r1 = client.post("/api/v1/runs", json=body, headers=h)
    r2 = client.post("/api/v1/runs", json=body, headers=h)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["run_id"] == r2.json()["run_id"]


def test_gate_evaluate_returns_signed_verdict(client: TestClient, verdict_checker):
    from run_replay import Recorder, RunMeta, StepKind
    # Record into the SAME state dir the app's gate reads from.
    state_dir = client.app.state.gate.state_dir
    tok = make_token("acme", "deploy-agent", secret="0" * 32)
    h = {"Authorization": f"Bearer {tok}"}
    run_id = client.post("/api/v1/runs", json={
        "agent_name": "deploy", "tenant_id": "acme", "idempotency_key": "api-2"},
        headers=h).json()["run_id"]
    rec = Recorder(state_dir=state_dir, meta=RunMeta(run_id=run_id, agent_name="deploy"))
    rec.step(StepKind.MODEL_CALL, "planner", inp={"x": 1}, out={"y": 2},
             state={"x": 1}, wall_ms=5.0)
    r = client.post("/api/v1/gate/evaluate",
                    json={"run_id": run_id, "agent_name": "deploy", "tenant_id": "acme",
                          "candidate_summary": "retry tweak"},
                    headers=h)
    assert r.status_code == 200
    v = r.json()
    assert v["decision"] in ("CERTIFY", "BLOCK")
    ok, _ = verdict_checker(client, v["verdict_id"], tok)
    assert ok is True


def test_unauthenticated_gate_rejected(client: TestClient):
    r = client.post("/api/v1/gate/evaluate",
                    json={"run_id": "x", "agent_name": "deploy", "tenant_id": "acme",
                          "candidate_summary": "z"})
    assert r.status_code in (401, 403)


def test_ssrf_guard_blocks_internal_hosts():
    # SSRF: must refuse to fetch cloud metadata / internal IPs
    assert is_ssrf_safe("https://169.254.169.254/latest/meta-data/") is False
    assert is_ssrf_safe("http://localhost:9000/") is False
    assert is_ssrf_safe("https://example.com/docs") is True
