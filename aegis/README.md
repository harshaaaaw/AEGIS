# AEGIS Control Plane - Package README

**Use this if you `pip install aegis-control`. For the full product, see the [root README](../README.md).**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](../../LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](#)
[![Tests](https://img.shields.io/badge/tests-85%20green-brightgreen.svg)](#quality)

## What this package is

`aegis-control` is the control plane library: gate, spine, bus, and ten subsystems. The root repo bundles five infrastructure packages it is built on (`run-replay`, `evalforge`, `agent-sentinel`, `token-governor`, `meshwork`). This package alone is importable and testable.

## Install

```bash
pip install -e ./aegis  # from repo root
# or after publish
pip install aegis-control
```

## Use - certify a run

```bash
cat > run.jsonl <<'EOF'
{"idx":0,"kind":"MODEL_CALL","name":"planner","in":{"x":1},"out":{"y":2},"state":{"x":1},"ms":5}
EOF
aegis certify run.jsonl
aegis verify <verdict_id>
aegis posture --tenant acme
```

```python
from aegis.gate import ShipGate
from aegis.spine import Spine, SpineConfig

spine = Spine(SpineConfig(db_path="./state/spine.db"))
gate = ShipGate(spine, state_dir="./state")
verdict = gate.evaluate(GateRequest(agent_name="support-bot", tenant_id="acme", traces=[...], eval_cases=[...]))
print(verdict.decision, verdict.certificate or verdict.block_reason)
```

## HTTP API

All endpoints require `Bearer` JWT (HS256, 32 byte secret floor). Rate limited by slowapi.

- `POST /api/v1/runs` - begin a run idempotently
- `POST /api/v1/gate/evaluate` - produce signed CERTIFY or BLOCK verdict
- `GET  /api/v1/verdicts/{verdict_id}` - tenant scoped verify
- `GET  /metrics` - Prometheus exposition of OTel counters

See `src/aegis/main.py` for request shapes.

## CLI reference

| Command | What it does |
|---|---|
| `aegis certify run.jsonl` | Decide CERTIFY or BLOCK for a recorded run |
| `aegis verify <verdict_id>` | Re check signature plus hash chain integrity |
| `aegis drift <run_id> base.jsonl live.jsonl` | Compare live outputs to certified baseline |
| `aegis posture --tenant acme` | Whole plane posture in one view |
| `aegis ssrf https://example.com` | Test the SSRF guard for a tool URL |
| `aegis server --port 8000` | Serve the HTTP API locally |

## Security model

- HMAC signed, hash chained verdicts, tenant scoped.
- Secrets must be 32 bytes or more. 11 byte secrets are rejected at boot.
- SSRF guard blocks metadata, loopback, and RFC1918 hosts.
- Bus subscribers are failure isolated. One crashing subsystem never breaks the others.
- Tamper evident Spine (SQLite) is the trust root.

Full model: [SECURITY.md](SECURITY.md)

## Quality

| Signal | Value |
|---|---|
| Tests | 85 green |
| Ruff | clean |
| Mypy | clean |
| Bandit | clean |

Run: `pytest aegis/tests -q`

## License

MIT - see [LICENSE](../../LICENSE)
