# Contributing to AEGIS

Thanks for looking at AEGIS. This repo is the control plane that certifies, governs, and proves enterprise AI agents. It is one of three products in the trust-loop suite (AEGIS, CAUSALA, SIMFORGE).

## How to run it locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ./aegis -e ./run-replay -e ./evalforge -e ./agent-sentinel -e ./token-governor -e ./meshwork
pip install ruff mypy bandit pytest pytest-cov
pytest -q
```

## What we expect from a PR

- Tests for every change. A test that passes if the function were deleted is decoration. We fail on missing failure-path tests (tenant denial, tamper, weak secret, rate limit).
- `ruff check .`, `mypy . --ignore-missing-imports`, and `bandit -r aegis run-replay evalforge agent-sentinel token-governor meshwork` stay clean in CI.
- No bare `except:` that swallows failures. Catch the specific error and log it with context (event id, subsystem, error).
- Every read-modify-write on shared state is idempotent (dedupe key on retry).
- Every public API call is anchored to the real library it uses, not a guessed signature.

## Commit style

Short, active, first-person. `certify verdict on replay`, `deny rival tenant on verify`, `reject secret under 32 bytes`. Link the issue or test that proves the change.

## Architecture

Read `aegis/ARCHITECTURE.md` (or the top-level `ARCHITECTURE.md`) before changing the control plane. The 10 subsystems boot in `aegis/src/aegis/control/plane.py`.

## Code of conduct

Be direct, be kind, no ego. We review the diff, not the person.
