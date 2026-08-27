# Contributing to AEGIS

Thanks for looking at AEGIS. AEGIS is a standalone control plane that certifies,
governs, and proves enterprise AI agents. It owns its trust primitives and imports
no other product.

## What lives here
- `aegis/` - the control plane (gate, spine, bus, ten subsystems)
- `run-replay/`, `evalforge/`, `agent-sentinel/`, `token-governor/`, `meshwork/` -
  the bundled infrastructure AEGIS is built on

## Local setup
```bash
python -m venv .venv && source .venv/Scripts/activate
pip install -e ./aegis -e ./run-replay -e ./evalforge -e ./agent-sentinel \
            -e ./token-governor -e ./meshwork
export AEGIS_JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(16))")
```

## Quality gate (runs in CI)
```bash
ruff check .
mypy . --ignore-missing-imports
bandit -r aegis run-replay evalforge agent-sentinel token-governor meshwork
pytest
```
A PR is green only when all four pass.

## Rules
- No cross-product imports. AEGIS must stand alone.
- Every subsystem writes to the Spine (tamper-evident) and registers on the bus.
- No bare except; typed raises carry a run or tenant id.
- Keep the audit contract real: idempotent run ids, externalized state.
