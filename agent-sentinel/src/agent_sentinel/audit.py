"""Hash-chained, append-only audit log with chain resumption and tamper proof."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path


class AuditLog:
    """One JSONL file per tenant-day. Entries commit to the hash of the
    previous entry, so editing or deleting history breaks verification.

    Writes are serialized under a lock; the file is opened in append mode
    and fsync'd so a crash never loses an acknowledged decision.
    """

    def __init__(self, root: str | os.PathLike):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._prev_hash = ""
        self._fh = None
        self._day = None

    def _file_for(self, ts: float) -> Path:
        day = time.strftime("%Y%m%d", time.gmtime(ts))
        return self.root / f"audit-{day}.jsonl"

    def _ensure_open(self, path: Path):
        if self._fh is not None and self._day == path.name:
            return
        if self._fh is not None:
            self._fh.close()
        fresh = not path.exists() or path.stat().st_size == 0
        self._fh = open(path, "a", encoding="utf-8")
        self._day = path.name
        if fresh:
            self._prev_hash = ""
        else:
            with open(path, "rb") as f:
                lines = [ln for ln in f.read().splitlines() if ln.strip()]
            self._prev_hash = json.loads(lines[-1])["hash"] if lines else ""

    def record(self, action: str, labels: list[str], reasons: list[str],
               channel: str, excerpt: str, ctx_ids: dict) -> dict:
        ts = time.time()
        entry = {
            "ts": round(ts, 3),
            "action": action,
            "channel": channel,
            "labels": labels,
            "reasons": reasons,
            "excerpt": excerpt[:160],
            **ctx_ids,
        }
        with self._lock:
            self._ensure_open(self._file_for(ts))
            entry["hash"] = self._hash(entry)
            self._fh.write(json.dumps(entry, separators=(",", ":")) + "\n")
            self._fh.flush()
            os.fsync(self._fh.fileno())
            self._prev_hash = entry["hash"]
        return entry

    def _hash(self, entry_no_hash: dict) -> str:
        payload = json.dumps(entry_no_hash, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(self._prev_hash.encode() + payload).hexdigest()

    # ---- verification -----------------------------------------------

    def verify(self) -> tuple[bool, int, str | None]:
        ok, n = True, 0
        prev_by_file: dict[Path, str] = {}
        for path in sorted(self.root.glob("audit-*.jsonl")):
            prev = ""
            data = path.read_bytes().splitlines()
            for raw in data:
                if not raw.strip():
                    continue
                e = json.loads(raw)
                claimed = e.pop("hash")
                expected = hashlib.sha256(
                    prev.encode() +
                    json.dumps(e, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                n += 1
                if claimed != expected:
                    return False, n, claimed
                prev = claimed
            prev_by_file[path] = prev
        return ok, n, None

    def close(self):
        if self._fh is not None:
            self._fh.close()
            self._fh = None
