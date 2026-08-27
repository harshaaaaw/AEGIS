# AEGIS

**The control plane that certifies, governs, and proves enterprise AI agents.**

AEGIS is a standalone platform: every AI agent a company runs gets tested before
launch, watched in production, governed by policy, valued by finance, and proven to
compliance. One audit trail, one posture view, ten subsystems sharing one backbone.

## The one problem it solves

"I have deployed AI across my business and I cannot trust that it is safe, know if
my providers silently changed it, prove what it is worth, control who sees what, or
show auditors I am compliant."

AEGIS is that single source of truth.

## What's inside (ten subsystems, one control plane)

1. **Ship Gate** - tests agents before launch (replay + eval + policy). Built on three
   real engines: run-replay (forensic recording), evalforge (the eval gate),
   agent-sentinel (per-turn security shield).
2. **SwapWatch** - detects silent model swaps and drift in production, reconciles SLA-cost.
3. **ROI Attest** - proves each AI initiative's value to the board, auditor-ready.
4. **Governed Memory** - role-scoped knowledge with provenance.
5. **Contract & Spend Intel** - reads AI vendor contracts for traps, benchmarks spend.
6. **Twin Truth** - keeps digital twins honest (drift + ROI).
7. **Causal Decisions** - a real OLS effect estimator with honest confidence intervals.
8. **Sim/RL Factory** - turns workflows into training/eval data for your own agents.
9. **Autonomous Ops** - claims execution + coordination workers.
10. **Audit & Compliance Trail** - one immutable, signed record across all nine.

## Why it is real, not a claim

- **One audit spine.** Every subsystem writes to the same tamper-evident Spine
  (SQLite-backed, idempotent run ids). That shared record is the moat.
- **Event-driven.** Subsystems communicate only through an in-process bus with
  per-subscriber failure isolation. No subsystem can block another.
- **Multi-tenant + JWT.** One identity model (OIDC-style JWT, 32-byte secret floor,
  SSRF guard) across every pane.
- **Your engines are three of the ten.** Ship Gate = run-replay + evalforge +
  agent-sentinel, productized and wired to the spine.

## Quickstart

```bash
python -m venv .venv && source .venv/Scripts/activate   # or bin/activate
pip install -e ./aegis -e ./run-replay -e ./evalforge -e ./agent-sentinel \
            -e ./token-governor -e ./meshwork
export AEGIS_JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(16))")
aegis boot --state-dir ./state
```

Run the gate on a recorded agent run:

```python
from aegis.gate import ShipGate
from aegis.spine import Spine, SpineConfig

spine = Spine(SpineConfig(db_path="./state/spine.db"))
gate = ShipGate(spine, state_dir="./state")
verdict = gate.evaluate(GateRequest(agent_name="support-bot", tenant_id="acme",
                                    traces=[...], eval_cases=[...]))
print(verdict.certificate or verdict.block_reason)
```

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

## Roadmap

- [ ] SwapWatch statistical drift test (Cohen's d, Welch t-test, BH correction).
- [ ] Governed Memory on Neo4j with ABAC read scopes.
- [ ] Contract Intel OCR + NER clause classifier.
- [ ] Twin Truth live fidelity-drift scoring.
- [ ] KEDA-scaled Autonomous Ops workers.

## Quality

- `pytest` across all six bundled packages (gate, spine, subsystems, replay,
  eval, shield, governor, meshwork).
- Static gates: `ruff`, `mypy --ignore-missing-imports`, `bandit` stay clean in CI.
- FastAPI surface: `POST /api/v1/gate/evaluate`, `POST /api/v1/runs`,
  `GET /api/v1/verdicts/{id}`, `GET /metrics` (Prometheus exposition).

## Honest limitations

- The spec envisions Kafka + signed S3 audit and Neo4j graph storage. This build
  uses an in-process bus and a SQLite spine to keep it local-first and runnable
  with zero infrastructure. The subsystem boundaries and audit contract are real;
  the storage backend is swappable.
- Subsystems 2-9 are implemented at varying depth: Ship Gate and Causal Decisions
  carry real logic; the others are wired rooms with focused behavior and are the
  natural next depth to build.

## Repo layout

```
aegis/          the control plane (gate, spine, bus, subsystems)
run-replay/     forensic recording of agent runs
evalforge/      golden-set eval harness with CI merge gates
agent-sentinel/ per-turn security shield
token-governor/ budget + kill-switch + cost accounting
meshwork/       resilient multi-agent workflows
```
