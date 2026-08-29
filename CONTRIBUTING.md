# Contributing to AEGIS

Thanks for looking at AEGIS. AEGIS is a standalone control plane that certifies, governs, and proves enterprise AI agents. It owns its trust primitives and imports no other product.

We treat contributor onboarding as the activation funnel. The goal is your first PR merged, not just opened.

## What lives here

- `aegis/` - the control plane (gate, spine, bus, ten subsystems)
- `run-replay/`, `evalforge/`, `agent-sentinel/`, `token-governor/`, `meshwork/` - the bundled infrastructure AEGIS is built on

## Local setup - 3 steps

```bash
python -m venv .venv && source .venv/Scripts/activate  # Windows: .venv\Scripts\activate
pip install -e ./aegis -e ./run-replay -e ./evalforge -e ./agent-sentinel -e ./token-governor -e ./meshwork
export AEGIS_JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(16))")
```

Verify:

```bash
pytest aegis/tests -q
aegis certify aegis/tests/fixtures/run.jsonl --help
```

## How to contribute

1. Fork the repo
2. Create a branch: `git checkout -b feature/your-feature`
3. Make your change with a test that proves it
4. Run the gate locally before pushing:

```bash
ruff check .
mypy aegis/src/aegis --config-file aegis/pyproject.toml
bandit -r aegis/src/aegis -q
pytest -q
```

5. Submit a PR with a clear description and test evidence. Link the issue if one exists.
6. Respond to review feedback. We keep iterations tight and respectful.

## What we look for in PRs

- Every subsystem writes to the Spine (tamper evident) and registers on the bus. Do not add in memory only state.
- No cross product imports. AEGIS must stand alone.
- No bare `except`. Typed raises must carry a run or tenant id.
- Keep the audit contract real: idempotent run ids, externalized state, tenant scope on every read.
- Add or update a test. A change without a test is not verifiable.
- Update docs if you change CLI or API shapes.

## Review promise

We triage every PR and issue within 48 hours. If you have not heard back in 48 hours, ping the PR - we missed it, not ignored it.

We label good first issues with `good first issue`. Those are scoped to be completable in a single sitting and we give extra review attention.

## Quality gate (runs in CI)

A PR is green only when all four pass:

- `ruff check`
- `mypy --ignore-missing-imports`
- `bandit -r ... -q`
- `pytest -q`

See `.github/workflows/quality-gate.yml` for the exact matrix (Python 3.11 and 3.14).

## Reporting security issues

Do not open a public issue for vulnerabilities. See [SECURITY.md](SECURITY.md) for the private reporting path.

## Code of conduct

Be kind, be direct, stay technical. We enforce a respectful review environment. Harassment or dismissive reviews are not tolerated.
