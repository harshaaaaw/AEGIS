"""Shared pytest fixtures: isolated SQLite spine + temp run-replay dir."""
from __future__ import annotations

from pathlib import Path

import pytest

from aegis.spine import Spine, SpineConfig

TEST_SECRET = "0" * 32  # 32-byte secret satisfies the entropy floor in security.py


@pytest.fixture
def tmp_state(tmp_path: Path) -> Path:
    """A temp dir usable as the run-replay state_dir (no real FS pollution)."""
    d = tmp_path / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def spine(tmp_path: Path) -> Spine:
    """A real Spine backed by a temp SQLite DB. Externalized state, isolated."""
    db = tmp_path / "aegis.db"
    cfg = SpineConfig(db_path=str(db), jwt_secret=TEST_SECRET, require_auth=False)
    return Spine(cfg)


@pytest.fixture
def client(tmp_path: Path):
    """A FastAPI TestClient wired to a temp Spine + state dir."""
    from aegis.main import build_app

    db = tmp_path / "aegis.db"
    state = tmp_path / "runs"
    state.mkdir(parents=True, exist_ok=True)
    app = build_app(db_path=str(db), state_dir=str(state), jwt_secret=TEST_SECRET)
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


@pytest.fixture
def verdict_checker():
    """Return a helper that independently fetches + verifies a verdict via the API."""
    def _check(client, verdict_id: str, token: str) -> tuple[bool, dict | None]:
        r = client.get(f"/api/v1/verdicts/{verdict_id}",
                       headers={"Authorization": f"Bearer {token}"})
        if r.status_code != 200:
            return False, None
        return r.json()["signature_valid"], r.json()
    return _check


def is_verdict_valid(client, verdict_id: str, token: str) -> tuple[bool, dict | None]:
    """Independently fetch + verify a verdict via the API (not trusting the create response)."""
    r = client.get(f"/api/v1/verdicts/{verdict_id}",
                   headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        return False, None
    return r.json()["signature_valid"], r.json()
