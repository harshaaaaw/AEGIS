# AEGIS Control Plane

**Trust, govern, and prove enterprise AI agents.**

AEGIS is a control plane: the room where ten agent subsystems live. It records every
agent run, decides whether a change is safe to ship, and produces tamper-evident
verdicts you can audit later. The one-liner:

> Enterprises running hundreds of AI agents touching money and production systems
> cannot control what each may do autonomously, nor prove it afterward. AEGIS gives
> each agent exactly as much freedom as it has earned, auto-demotes violators, and
> hands regulators receipts.

## What it actually does

- **Certifies a run** via forensic replay + shield + eval, and signs the verdict
  (HMAC + hash chain).
- **Blocks a ship** when the replay breaks a shield, the eval fails, or the causal
  invariant is violated.
- **Watches for drift** after certification (live run vs certified baseline).
- **Attests ROI** on a tamper-evident ledger with no fake numbers.
- **Stresses the agent** through Sim/RL Factory, which turns production failures into
  golden regression cases.
- **Graduated trust** from shadow to autonomous, with instant demotion on violation.
- **One-view posture** of the whole plane (Panes).

## The 10 subsystems (the room)

1. **Ship Gate**: certify/block a change via forensic replay + shield + eval.
2. **SwapWatch**: flags behavior drift after certification.
3. **ROI Attest**: tamper-evident cost/benefit ledger (no fake ROI).
4. **Governed Memory**: versioned, capability-gated agent memory.
5. **Contract Intel**: blocks unauthorized tool calls (scope creep).
6. **Twin Truth**: digital-twin counterfactual simulation.
7. **Causal Decisions**: real OLS effect estimator with honest CI.
8. **Sim/RL Factory**: turns production failures into regression cases.
9. **Autonomous Ops**: graduated trust (shadow to autonomous).
10. **Panes**: one-view posture of the whole plane.

## How AEGIS compares (the moat)

| Capability | Spreadsheet + logs | Vendor point tool | AEGIS |
|---|---|---|---|
| Pre-merge certification gate | no | one dimension | replay + shield + eval |
| Tamper-evident verdict + hash chain | no | rarely | yes |
| Drift watch after ship | no | partial | yes |
| ROI attest on one ledger | manual | no | yes |
| Ten subsystems on one spine | no | no | yes |
| Multi-tenant, JWT + SSRF guard | varies | varies | first-class |

The differentiator is the shared audit Spine: one signed record proves an agent passed
the gate, ran, was attested, and accessed memory under a role. That cross-subsystem
proof is what a buyer defends to a board.

## Quickstart

```bash
pip install -e ./aegis -e ./run-replay -e ./evalforge -e ./agent-sentinel \
            -e ./token-governor -e ./meshwork
export AEGIS_JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(16))")

# 1. Certify a recorded agent run (JSONL of steps)
cat > run.jsonl <<'EOF'
{"idx":0,"kind":"MODEL_CALL","name":"planner","in":{"x":1},"out":{"y":2},"state":{"x":1},"ms":5}
EOF
aegis certify run.jsonl

# 2. Re-verify a verdict's signature + hash chain
aegis verify <verdict_id>

# 3. Check behavior drift (live run vs certified baseline)
aegis drift run-1 baseline.jsonl live.jsonl

# 4. Whole control-plane posture in one view
aegis posture --tenant acme

# 5. SSRF guard check for an agent tool URL
aegis ssrf http://169.254.169.254/latest

# 6. Serve the HTTP API locally
aegis server --port 8000
```

## HTTP API

All endpoints require a `Bearer` JWT (HS256, >=32-byte secret). Rate limited.

- `POST /api/v1/runs`: begin (idempotent) a run
- `POST /api/v1/gate/evaluate`: produce a signed CERTIFY/BLOCK verdict
- `GET  /api/v1/verdicts/{verdict_id}`: tenant-scoped verify
- `GET  /metrics`: Prometheus exposition of OTel counters

## Security model

- HMAC-signed, hash-chained verdicts; tenant-scoped.
- Secrets must be >=32 bytes; 11-byte secrets are rejected at the gate.
- SSRF guard blocks metadata/loopback/RFC1918 hosts.
- Bus subscribers are failure-isolated (chaos-tested: one crashing subsystem never
  breaks the others).
- Tamper-evident Spine (SQLite) is the trust root.

## Roadmap

- [ ] SwapWatch: statistical drift test (Cohen's d, Welch t-test, BH correction).
- [ ] Governed Memory: Neo4j-backed graph with ABAC read scopes.
- [ ] Contract Intel: OCR + NER clause classifier over vendor PDFs.
- [ ] Twin Truth: live fidelity-drift scoring against telemetry.
- [ ] Autonomous Ops: KEDA-scaled claims execution workers.

## Quality (measured)

| Signal | Value |
|---|---|
| Tests | 85 green |
| Ruff | clean |
| Mypy (business logic) | clean |
| Bandit | clean |

Run: `pytest aegis/tests/ -q`

## Honest limitations

- The demo agent in the CLI exists so the CLI works out of the box.
- The spec envisions Kafka + signed S3 audit and Neo4j storage; this build uses an
  in-process bus and SQLite Spine to stay local-first and runnable with zero
  infrastructure. The subsystem boundaries and audit contract are real; the storage
  backend is swappable.
- Agent autonomy ladder L0 to L4 is in the blueprint; the v0 rooms ship the
  certification, drift, ROI, and posture primitives the ladder builds on.

## License

MIT.
