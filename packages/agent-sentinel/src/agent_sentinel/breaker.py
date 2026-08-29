"""Per-tenant circuit breakers and counters.

If a tenant's traffic turns hostile (injection rate spikes) or noisy
(budget breaches), the shield can fail closed for that tenant only,
without touching anyone else. Counters are fixed-window; this is
deliberately simple enough to reason about under audit.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class Window:
    started: float = field(default_factory=time.time)
    events: int = 0


@dataclass
class BreakerConfig:
    max_events_per_window: int = 10      # trips after N adverse events...
    window_seconds: float = 60.0         # ...within this window
    cooldown_seconds: float = 300.0      # stay open this long after tripping


class CircuitBreaker:
    """Per-key (tenant or session) breaker over an adverse-event counter."""

    def __init__(self, cfg: BreakerConfig | None = None):
        self.cfg = cfg or BreakerConfig()
        self._lock = threading.Lock()
        self._windows: dict[str, Window] = {}
        self._open_until: dict[str, float] = {}

    def record_adverse(self, key: str) -> bool:
        """Count one adverse event. Returns True if this event TRIPPED the breaker."""
        now = time.time()
        with self._lock:
            if self.is_open(key, now):
                return False
            w = self._windows.get(key)
            if w is None or now - w.started > self.cfg.window_seconds:
                w = Window(started=now, events=0)
                self._windows[key] = w
            w.events += 1
            if w.events >= self.cfg.max_events_per_window:
                self._open_until[key] = now + self.cfg.cooldown_seconds
                self._windows.pop(key, None)
                return True
            return False

    def is_open(self, key: str, now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        until = self._open_until.get(key)
        if until is None:
            return False
        if now >= until:
            del self._open_until[key]      # cooldown served, half-open again
            return False
        return True

    def state(self, key: str) -> str:
        return "open" if self.is_open(key) else "closed"
