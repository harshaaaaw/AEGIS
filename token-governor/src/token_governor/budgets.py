"""Budgets: per-tenant and per-workflow daily caps with soft/hard thresholds.

Design: counters are (day, key) scoped, monotone, and updated atomically
under a lock. A HARD cap refuses new spend for the rest of the UTC day
unless an explicit override is granted. SOFT thresholds fire alerts once.
"""

from __future__ import annotations

import threading

from .models import SpendStatus, today_key


class Budgets:
    def __init__(self):
        self._lock = threading.Lock()
        # (day, scope_kind, key) -> {"cap": float, "soft": float, "spent": float,
        #                            "soft_fired": bool}
        self._books: dict[tuple, dict] = {}

    def set_cap(self, kind: str, key: str, cap_usd: float,
                soft_frac: float = 0.8, day: str | None = None):
        """Declare a daily cap. kind: 'tenant' | 'workflow'."""
        if kind not in ("tenant", "workflow"):
            raise ValueError(f"kind must be 'tenant' or 'workflow', got {kind!r}")
        d = day or today_key()
        with self._lock:
            self._books.setdefault((d, kind, key), {
                "cap": float(cap_usd),
                "soft": float(cap_usd) * soft_frac,
                "spent": 0.0,
                "soft_fired": False,
            })

    def _book(self, kind: str, key: str) -> dict | None:
        return self._books.get((today_key(), kind, key))

    def precheck(self, tenant_id: str, workflow: str,
                 est_cost_usd: float) -> SpendStatus:
        """Called BEFORE a model call. Returns worst status across scopes."""
        status = SpendStatus.OK
        with self._lock:
            for kind, key in (("tenant", tenant_id), ("workflow", f"{tenant_id}:{workflow}")):
                b = self._book(kind, key)
                if b is None:
                    continue
                projected = b["spent"] + est_cost_usd
                if projected > b["cap"]:
                    return SpendStatus.HARD          # strictest wins immediately
                if projected > b["soft"]:
                    status = SpendStatus.SOFT
        return status

    def commit(self, tenant_id: str, workflow: str, cost_usd: float) -> list[str]:
        """Apply actual spend; returns alert events ('SOFT_x', 'HARD_x')."""
        events = []
        with self._lock:
            for kind, key in (("tenant", tenant_id), ("workflow", f"{tenant_id}:{workflow}")):
                b = self._book(kind, key)
                if b is None:
                    continue
                b["spent"] += cost_usd
                if not b["soft_fired"] and b["spent"] >= b["soft"]:
                    b["soft_fired"] = True
                    events.append(f"SOFT_{kind.upper()}:{key}")
                if b["spent"] >= b["cap"]:
                    events.append(f"HARD_{kind.upper()}:{key}")
        return events

    def spent(self, kind: str, key: str) -> float:
        with self._lock:
            b = self._book(kind, key)
            return b["spent"] if b else 0.0

    def remaining(self, kind: str, key: str) -> float:
        with self._lock:
            b = self._book(kind, key)
            return max(0.0, b["cap"] - b["spent"]) if b else float("inf")
