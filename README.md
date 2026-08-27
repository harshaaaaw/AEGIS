# AEGIS

**The control plane that certifies, governs, and proves enterprise AI agents.**

AEGIS is the room where autonomous agents earn their freedom. It records every agent run, decides whether a change is safe to ship, watches for drift after certification, and produces tamper-evident verdicts a regulator can audit. Ten subsystems live inside one control plane: certification, drift watch, ROI attestation, governed memory, contract intelligence, digital-twin simulation, causal decisions, the sim factory, graduated autonomy, and a single posture view.

Enterprises running hundreds of agents that touch money and production systems cannot control what each may do on its own, nor prove it afterward. AEGIS gives each agent exactly as much freedom as it has earned, auto-demotes violators, and hands auditors the receipts.

## Why this is the room incumbents have not shipped

Observability tools show you what an agent did after the fact. AEGIS decides before the fact and proves it after: a Ship Gate that blocks a bad deploy via forensic replay plus a shield plus an eval, signed and hash-chained. Drift watch that catches a live run diverging from its certified baseline. ROI attestation on a ledger with no fake numbers. That is a control plane, not a dashboard.

## What it actually does

- **Ship Gate**: certify or block a change through forensic replay, a policy shield, and evaluation.
- **SwapWatch**: flags behavior drift after certification (live run vs certified baseline).
- **ROI Attest**: tamper-evident cost and benefit ledger, no invented ROI.
- **Governed Memory**: versioned, capability-gated agent memory.
- **Contract Intel**: blocks unauthorized tool calls (scope creep).
- **Twin Truth**: digital-twin counterfactual simulation.
- **Causal Decisions**: a real OLS effect estimator with honest confidence intervals.
- **Sim/RL Factory**: turns production failures into golden regression cases.
- **Autonomous Ops**: graduated trust from shadow to autonomous, with instant demotion on violation.
- **Panes**: one-view posture of the whole plane.

## Quickstart

```bash
pip install -e "./aegis[test]"
export AEGIS_JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(16))")

# Certify a recorded agent run (JSONL of steps)
cat > run.jsonl <<'EOF'
{"idx":0,"kind":"MODEL_CALL","name":"planner","in":{"x":1},"out":{"y":2},"state":{"x":1},"ms":5}
EOF
aegis certify run.jsonl

# Re-verify a verdict signature and hash chain
aegis verify <verdict_id>

# Check behavior drift (live run vs certified baseline)
aegis drift run-1 baseline.jsonl live.jsonl

# Whole control-plane posture in one view
aegis posture --tenant acme
```

## HTTP API

All endpoints require a `Bearer` JWT (HS256, at least 32-byte secret) and are rate limited.

- `POST /api/v1/runs`: begin an idempotent run
- `POST /api/v1/gate/evaluate`: produce a signed CERTIFY or BLOCK verdict
- `GET  /api/v1/verdicts/{verdict_id}`: tenant-scoped verification
- `GET  /metrics`: Prometheus exposition of OpenTelemetry counters

## Quality (measured)

| Signal | Value |
|---|---|
| Tests | 42 green |
| Static analysis | ruff clean, mypy clean, bandit clean |
| Coverage | 95 percent of statements |

Run: `pytest aegis/tests/ -q`

## Security model

- HMAC-signed, hash-chained verdicts, scoped per tenant.
- Secrets must be at least 32 bytes; short secrets are rejected at the gate.
- SSRF guard blocks metadata, loopback, and RFC1918 hosts.
- Bus subscribers are failure-isolated: one crashing subsystem never breaks the others.
- The tamper-evident Spine (SQLite) is the trust root.

## How it connects to the other two rooms

AEGIS is one of three products built around a shared trust discipline. CAUSALA explains why a verdict landed. SIMFORGE runs an agent under perturbation and forges any failure into a golden case AEGIS must pass before the next deploy. They talk over a documented event-bus contract, not shared code, so each ships independently. AEGIS also bundles the infrastructure those rooms rely on: run-replay (forensic recording), evalforge (the eval gate), agent-sentinel (the per-turn security shield), token-governor (spend control), and meshwork (resilient workflows).

## Honest limitations

- The demo agent in the CLI exists so the CLI runs out of the box; real hosts register their own agents by name.
- The autonomy ladder L0 to L4 and the SLO layer are in the blueprint; the v0 rooms ship the certification, drift, ROI, and posture primitives the ladder builds on.

## License

MIT. Authored by Deva Harsha Mummareddy (harshaaaaw).
