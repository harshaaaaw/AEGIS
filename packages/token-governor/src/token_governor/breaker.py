"""Circuit breakers for runaway agents.

A stuck agent loop (retry storms, infinite tool cycles) is the classic
production incident: nothing is "wrong" per call, the bill just climbs.
Breakers watch rolling windows per session and trip on:

  - max spend per session window
  - max calls per session window
  - consecutive failures without progress

Tripped breakers refuse new calls until cooldown. This module holds no
model logic; it is pure accounting, so it stays auditable.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class BreakerPolicy:
    window_seconds: float = 300.0
    max_spend_usd: float = 5.00          # per session per window
    max_calls: int = 120                 # per session per window
    max_consecutive_failures: int = 5    # progress-less calls
    cooldown_seconds: float = 900.0


@dataclass
class _Window:
    started: float
    spend: float = 0.0
    calls: int = 0


class RunawayBreaker:
    def __init__(self, policy: BreakerPolicy | None = None):
        self.policy = policy or BreakerPolicy()
        self._lock = threading.RLock()      # reentrant: observe() inspects state while holding
        self._windows: dict[str, _Window] = {}
        self._fail_streaks: dict[str, int] = {}
        self._open_until: dict[str, float] = {}

    # ---- metering ----------------------------------------------------

    def observe(self, session_id: str, cost_usd: float, failed: bool = False):
        now = time.time()
        with self._lock:
            w = self._windows.get(session_id)
            if w is None or now - w.started > self.policy.window_seconds:
                w = _Window(started=now)
                self._windows[session_id] = w
            w.spend += cost_usd
            w.calls += 1

            streak = 0 if not failed else self._fail_streaks.get(session_id, 0) + 1
            self._fail_streaks[session_id] = streak

            already_open = (session_id in self._open_until
                            and now < self._open_until[session_id])
            tripped = (
                w.spend > self.policy.max_spend_usd
                or w.calls > self.policy.max_calls
                or streak >= self.policy.max_consecutive_failures
            )
            if tripped and not already_open:
                self._open_until[session_id] = now + self.policy.cooldown_seconds

    def reset_streak(self, session_id: str):
        with self._lock:
            self._fail_streaks[session_id] = 0

    # ---- gating ------------------------------------------------------

    def allow(self, session_id: str) -> tuple[bool, str]:
        now = time.time()
        with self._lock:
            until = self._open_until.get(session_id)
            if until is None:
                return True, ""
            if now >= until:
                del self._open_until[session_id]
                self._windows.pop(session_id, None)
                return True, "cooldown served"
            return False, f"breaker open for another {until - now:.0f}s"

    def is_open(self, session_id: str, now: float | None = None) -> bool:
        ok, _ = self.allow(session_id)
        return not ok
