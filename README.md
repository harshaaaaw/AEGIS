# AEGIS - The open source control plane for enterprise AI agents

**Certify every agent before it ships. Watch it after. Prove it to auditors.**

[![GitHub stars](https://img.shields.io/github/stars/harshaaaaw/aegis?style=social)](https://github.com/harshaaaaw/aegis)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Build](https://img.shields.io/github/actions/workflow/status/harshaaaaw/aegis/quality-gate.yml?branch=master&label=build)](https://github.com/harshaaaaw/aegis/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](aegis/pyproject.toml)
[![Version](https://img.shields.io/badge/version-0.1.0-black.svg)](https://github.com/harshaaaaw/aegis/releases)

[Demo](#quickstart) · [Documentation](aegis/README.md) · [Architecture](#architecture) · [Roadmap](ROADMAP.md) · [Security](SECURITY.md)

> AEGIS is an open source AI agent control plane - certify, govern, and prove every agent run on a tamper-evident spine. One room where ten subsystems share one audit trail, one identity model, and one posture view.

![AEGIS demo](https://via.placeholder.com/1200x600/0a0a0a/00ff88?text=AEGIS+Terminal+Demo+%3A+aegis+certify+run.jsonl+%E2%86%92+CERTIFY+%7C+BLOCK)

### Trusted by builders who ship agents to production

AEGIS exists because enterprises running hundreds of AI agents touching money and production systems cannot control what each may do autonomously, nor prove it afterward.

## The problem in 3 sentences

You have deployed AI across your business and you cannot trust that it is safe, know if your providers silently changed a model, prove what it is worth, control who sees what, or show auditors you are compliant. You have 6 separate tools and no single source of truth. AEGIS is that single source of truth - one audit trail, one posture view.

## Why teams choose AEGIS

- **Stop unsafe agents before the merge** - replay + shield + eval gate blocks risky changes automatically, so shipping stays fast and safe.
- **Catch silent drift after ship** - SwapWatch fingerprints behavior and alerts when a model or tool changes under you, so SLA cost stays honest.
- **Hand regulators receipts** - every verdict is HMAC signed and hash chained with tenant scope, so audits are a query not a project.

## Quickstart - 3 steps, under 2 minutes

Copy paste on a clean machine. No Kubernetes, no JWT setup, no secret to find.

```bash
# 1. Clone and install (one command installs the control plane and its engines)
git clone https://github.com/harshaaaaw/aegis.git && cd aegis
python -m venv .venv && source .venv/Scripts/activate  # Windows: .venv\Scripts\activate
pip install -e ./aegis -e ./run-replay -e ./evalforge -e ./agent-sentinel -e ./token-governor -e ./meshwork

# 2. Certify a recorded run (JSONL of steps - works out of the box with no secret)
cat > run.jsonl <<'EOF'
{"idx":0,"kind":"MODEL_CALL","name":"planner","in":{"x":1},"out":{"y":2},"state":{"x":1},"ms":5}
EOF
aegis certify run.jsonl

# 3. Re-verify the receipt
aegis verify <verdict_id>
# -> {"valid": true, "decision": "CERTIFY"}
```

You will see `{"decision": "CERTIFY"}` or `{"decision": "BLOCK", "reason": "..."}`. Every decision is signed and can be re verified later.

**Python path:**

```python
from aegis.gate import ShipGate
from aegis.spine import Spine, SpineConfig

spine = Spine(SpineConfig(db_path="./state/spine.db"))
gate = ShipGate(spine, state_dir="./state")
verdict = gate.evaluate(GateRequest(agent_name="support-bot", tenant_id="acme", traces=[...], eval_cases=[...]))
print(verdict.certificate or verdict.block_reason)
```

**HTTP path:**

```bash
export AEGIS_JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(16))")
aegis server --port 8000
# POST /api/v1/gate/evaluate  Bearer <jwt>  ->  signed verdict
```

[Full quickstart and CLI reference →](aegis/README.md#quickstart)

## Features - scannable, not walls

| Capability | Description |
|---|---|
| Ship Gate | Certifies a run via forensic replay + per turn shield + golden set eval. Blocks merges that break policy. |
| SwapWatch | Detects behavior drift live vs certified baseline. Reconciles SLA cost. |
| ROI Attest | Tamper evident cost and benefit ledger. No fake numbers, real attestation. |
| Governed Memory | Versioned agent memory with capability checks and provenance. |
| Contract Intel | Blocks unauthorized tool calls and scope creep before execution. |
| Twin Truth | Counterfactual twin simulation to test what if without touching prod. |
| Causal Decisions | OLS effect estimator with honest confidence intervals, not point claims. |
| Sim/RL Factory | Turns prod failures into golden regression cases for the next gate. |
| Autonomous Ops | Graduated trust from shadow to autonomous, with instant demotion on violation. |
| Panes | One view posture of the whole plane for CISO, CFO and CTO. |

Each subsystem writes to the same tamper evident Spine and speaks only through the event bus. No subsystem can block another.

## Want governed AI without building this yourself?

This repo is the open core - fully self hostable, MIT licensed, useful alone. **AEGIS Cloud** adds SSO, RBAC, audit vault, and hosted run replay.

[**Try Cloud free**](https://github.com/harshaaaaw/aegis) | [Book a demo](https://github.com/harshaaaaw/aegis/discussions)

## Architecture - how it works in 10 seconds

```mermaid
graph TB
  CI[CI plugin] --> Gate[Ship Gate<br/>replay + shield + eval]
  Prod[Prod traffic] --> Watch[SwapWatch<br/>drift + SLA]
  Agent[Agent runtime] --> Bus{Event Bus}
  Bus --> Gate
  Bus --> Watch
  Bus --> Memory[Governed Memory]
  Bus --> Contract[Contract Intel]
  Bus --> Twin[Twin Truth]
  Bus --> Causal[Causal Decisions]
  Bus --> Sim[Sim/RL Factory]
  Bus --> Ops[Autonomous Ops]
  Gate --> Spine[(Spine<br/>SQLite hash chain)]
  Watch --> Spine
  Memory --> Spine
  Spine --> Panes[Panes<br/>one posture view]
  Panes --> CISO[CISO]
  Panes --> CFO[CFO]
  Panes --> CTO[CTO]
```

One K8s namespace in production. One process on your laptop. Same contracts, no infra needed to try.

[Deep architecture →](aegis/README.md#architecture) · [Security model →](SECURITY.md)

## How AEGIS compares

| Capability | Spreadsheet + logs | Vendor point tool | AEGIS |
|---|---|---|---|
| Pre merge certification gate | no | one dimension | replay + shield + eval |
| Tamper evident verdict + hash chain | no | rarely | yes |
| Drift watch after ship | no | partial | yes |
| ROI attest on one ledger | manual | no | yes |
| Ten subsystems on one spine | no | no | yes |
| Multi tenant, JWT + SSRF guard | varies | varies | first class |

The moat is the shared audit Spine: one signed record proves an agent passed the gate, ran, was attested, and accessed memory under a role. That cross subsystem proof is what a buyer defends to a board.

## Honest limitations

- The spec envisions Kafka + signed S3 audit and Neo4j storage. This build uses an in process bus and SQLite spine to stay local first and runnable with zero infra. Subsystem boundaries and audit contract are real, storage backend is swappable.
- Subsystems 2 to 9 ship at varying depth: Ship Gate and Causal Decisions carry real logic, the others are wired rooms with focused behavior and are the natural next depth to build.
- The eval pipeline stand in concatenates outputs. Wire a real candidate pipeline before relying on it for ship decisions.

## Roadmap

- [ ] SwapWatch statistical drift test (Cohen d, Welch t test, BH correction)
- [ ] Governed Memory on Neo4j with ABAC read scopes
- [ ] Contract Intel OCR plus NER clause classifier
- [ ] Twin Truth live fidelity drift scoring
- [ ] KEDA scaled Autonomous Ops workers
- [ ] Helm chart with OIDC and S3 audit backend

See [ROADMAP.md](ROADMAP.md) for timeline and design notes.

## Quality - measured, not claimed

| Signal | Value |
|---|---|
| Tests | 85 green |
| Ruff | clean |
| Mypy (business logic) | clean |
| Bandit | clean |

```bash
pytest aegis/tests -q
ruff check .
mypy aegis/src/aegis --config-file aegis/pyproject.toml
bandit -r aegis/src/aegis
```

## Contributing - we respond in 48 hours

1. Fork the repo
2. Create a branch: `git checkout -b feature/your-feature`
3. Run the gate: `pytest -q && ruff check .`
4. Submit a PR with a clear description of your change and test evidence

We triage every PR and issue within 48 hours. See [CONTRIBUTING.md](CONTRIBUTING.md) for good first issues and the quality gate.

## Security

See [SECURITY.md](SECURITY.md) for reporting, trust boundaries, and cryptographic guarantees. Please do not open public issues for vulnerabilities.

## License

MIT © [Deva Harsha Mummareddy](https://github.com/harshaaaaw) - see [LICENSE](LICENSE)

---

[![Star History Chart](https://api.star-history.com/svg?repos=harshaaaaw/aegis&type=Date)](https://star-history.com/#harshaaaaw/aegis&Date)

If AEGIS helped you ship safer agents, leave a star. It helps others find the project.
