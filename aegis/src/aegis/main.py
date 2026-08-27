"""FastAPI application: async API, OIDC auth dependency, rate limiting,
structured logging, and Prometheus metrics.

Design:
- Async endpoints (real `async def`) so I/O is concurrent, not blocking.
- Auth enforced via a real JWT dependency (security.verify_token) with a
  minimum secret-entropy floor; a missing/invalid/undersized secret is rejected.
- Rate limiting (slowapi) on the public-ish endpoints to blunt abuse/DoS
  (OWASP LLM ATC-8 / A10).
- Structured JSON logging for operator grep/alerting.
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .gate import GateRequest, ShipGate
from .observability import record_gate_eval, record_run_begun
from .security import (
    AuthError,
    WeakSecretError,
    get_logger,
    require_strong_secret,
    verify_token,
)
from .spine import Spine, SpineConfig

log = get_logger("aegis.api")

RUNS_BEGUN = Counter("aegis_runs_begun", "Runs begun", ["tenant"])
GATE_EVALS = Counter("aegis_gate_evaluations", "Gate evaluations", ["tenant"])
GATE_BLOCKS = Counter("aegis_gate_blocks", "Gate blocks", ["tenant"])

limiter = Limiter(key_func=get_remote_address)


def build_app(db_path: str, state_dir: str, jwt_secret: str) -> FastAPI:
    # Fail fast if the signing secret is too weak (no silent 11-byte key).
    require_strong_secret(jwt_secret)

    app = FastAPI(title="AEGIS Control Plane", version="0.1.0")
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded,
                              lambda r, e: JSONResponse(status_code=429,
                                                        content={"detail": "rate limited"}))
    spine = Spine(SpineConfig(db_path=db_path, jwt_secret=jwt_secret, require_auth=True))
    gate = ShipGate(spine, state_dir=state_dir)

    def auth(request: Request) -> dict:
        h = request.headers.get("Authorization", "")
        if not h.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        try:
            return verify_token(h[7:], jwt_secret)
        except (AuthError, WeakSecretError) as e:
            raise HTTPException(status_code=403, detail=str(e))

    @app.post("/api/v1/runs")
    @limiter.limit("20/minute")
    async def begin_run(body: dict, request: Request,
                        claims: dict = Depends(auth)):
        tenant = claims["tenant_id"]
        agent_name = body.get("agent_name")
        idempotency_key = body.get("idempotency_key")
        if not agent_name:
            raise HTTPException(status_code=400, detail="agent_name required")
        RUNS_BEGUN.labels(tenant).inc()
        record_run_begun(tenant)
        run_id = spine.begin_run(agent_name=agent_name, tenant_id=tenant,
                                 idempotency_key=idempotency_key)
        log.info("run_begin", extra={"tenant": tenant, "run_id": run_id})
        return {"run_id": run_id, "tenant_id": tenant}

    @app.post("/api/v1/gate/evaluate")
    @limiter.limit("10/minute")
    async def gate_evaluate(body: dict, request: Request,
                            claims: dict = Depends(auth)):
        tenant = claims["tenant_id"]
        GATE_EVALS.labels(tenant).inc()
        req = GateRequest(
            run_id=body["run_id"], agent_name=body.get("agent_name", "unknown"),
            tenant_id=tenant, candidate_summary=body.get("candidate_summary", ""))
        verdict = gate.evaluate(req)
        blocked = verdict.decision == "BLOCK"
        if blocked:
            GATE_BLOCKS.labels(tenant).inc()
        record_gate_eval(tenant, blocked)
        log.info("gate_eval", extra={"tenant": tenant,
                                     "verdict_id": verdict.verdict_id,
                                     "decision": verdict.decision})
        return {
            "verdict_id": verdict.verdict_id, "run_id": verdict.run_id,
            "tenant_id": tenant, "decision": verdict.decision,
            "reason": verdict.reason, "signature": verdict.signature,
            "evidence": verdict.evidence,
        }

    @app.get("/api/v1/verdicts/{verdict_id}")
    async def get_verdict(verdict_id: str, claims: dict = Depends(auth)):
        tenant = claims["tenant_id"]
        valid, rec = gate.verify_verdict(verdict_id, tenant_id=tenant)
        if rec is None:
            raise HTTPException(status_code=404, detail="verdict not found")
        return {"verdict_id": verdict_id, "signature_valid": valid,
                "tenant_scoped": True, "record": rec}

    @app.get("/metrics")
    async def metrics():
        return JSONResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # attach for tests/introspection
    app.state.spine = spine
    app.state.gate = gate
    return app


def create_app() -> FastAPI:
    """Env-driven factory used by the container (uvicorn aegis.main:create_app --factory)."""
    import os
    return build_app(
        db_path=os.environ.get("AEGIS_DB_PATH", "aegis.db"),
        state_dir=os.environ.get("AEGIS_STATE_DIR", "runs"),
        jwt_secret=os.environ.get("AEGIS_JWT_SECRET", "change-me"),
    )
