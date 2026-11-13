"""Thread-safe idempotency and content-hash deduplication engine with restart persistence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import threading
import time
from typing import Any, Dict, Optional, Tuple


class IdempotencyEngine:
    """Detects and suppresses duplicate event ingestion across external telecom sources.
    
    Supports optional restart persistence via append-only JSONL storage.
    """

    def __init__(
        self,
        ttl_seconds: float = 86400.0,
        storage_path: Optional[Path | str] = None,
    ):
        self.ttl_seconds = ttl_seconds
        self._lock = threading.RLock()
        self._storage_path: Optional[Path] = Path(storage_path) if storage_path else None
        # Maps deduplication_key -> (first_seen_timestamp, canonical_id)
        self._cache: Dict[str, Tuple[float, Optional[str]]] = {}

        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_from_storage()

    def _load_from_storage(self) -> None:
        """Load deduplication entries from persistent storage on startup."""
        if not self._storage_path or not self._storage_path.exists():
            return

        now = time.time()
        try:
            with self._storage_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        k = record["key"]
                        ts = float(record["first_seen"])
                        cid = record.get("canonical_id")
                        # Prune expired on load
                        if (now - ts) <= self.ttl_seconds:
                            self._cache[k] = (ts, cid)
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
        except Exception:
            # Storage read error fails safe with whatever in-memory cache exists
            pass

    def _append_to_storage(self, key: str, first_seen: float, canonical_id: Optional[str]) -> None:
        """Append a newly committed deduplication key to persistent storage."""
        if not self._storage_path:
            return
        try:
            payload = json.dumps({"key": key, "first_seen": first_seen, "canonical_id": canonical_id})
            with self._storage_path.open("a", encoding="utf-8") as f:
                f.write(payload + "\n")
        except Exception:
            pass

    def persist_snapshot(self) -> None:
        """Atomically persist current in-memory cache to disk, pruning expired entries."""
        if not self._storage_path:
            return
        now = time.time()
        with self._lock:
            self._cleanup_expired(now)
            try:
                temp_file = self._storage_path.with_suffix(".tmp")
                with temp_file.open("w", encoding="utf-8") as f:
                    for k, (ts, cid) in self._cache.items():
                        line = json.dumps({"key": k, "first_seen": ts, "canonical_id": cid})
                        f.write(line + "\n")
                temp_file.replace(self._storage_path)
            except Exception:
                pass

    def compute_key(
        self,
        source_system: str,
        external_event_id: Optional[str],
        raw_payload: Dict[str, Any],
    ) -> str:
        """Compute stable deduplication key from source and payload hash."""
        if external_event_id:
            # Deterministic prefix using source system + external ID
            return f"{source_system.upper()}::{str(external_event_id).strip()}"

        # Fallback to normalized content SHA-256 hash
        payload_bytes = json.dumps(raw_payload, sort_keys=True, default=str).encode("utf-8")
        h = hashlib.sha256(payload_bytes).hexdigest()
        return f"{source_system.upper()}::HASH::{h}"

    def check_and_record(
        self,
        dedup_key: str,
        canonical_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Check if key has already been processed. Returns (is_duplicate, existing_canonical_id)."""
        now = time.time()
        with self._lock:
            self._cleanup_expired(now)
            if dedup_key in self._cache:
                _, existing_id = self._cache[dedup_key]
                return True, existing_id

            self._cache[dedup_key] = (now, canonical_id)
            self._append_to_storage(dedup_key, now, canonical_id)
            return False, canonical_id

    def update_canonical_id(self, dedup_key: str, canonical_id: str) -> None:
        """Associate the resolved canonical ID with an existing deduplication key."""
        with self._lock:
            if dedup_key in self._cache:
                first_seen, _ = self._cache[dedup_key]
                self._cache[dedup_key] = (first_seen, canonical_id)
                self._append_to_storage(dedup_key, first_seen, canonical_id)

    def remove(self, dedup_key: str) -> bool:
        """Remove a deduplication key (e.g. if ingestion failed before completion)."""
        with self._lock:
            if dedup_key in self._cache:
                del self._cache[dedup_key]
                self.persist_snapshot()
                return True
            return False

    def _cleanup_expired(self, current_time: float) -> None:
        """Prune keys older than TTL."""
        expired = [k for k, (ts, _) in self._cache.items() if (current_time - ts) > self.ttl_seconds]
        for k in expired:
            del self._cache[k]

    def clear(self) -> None:
        """Clear the deduplication cache (useful in tests)."""
        with self._lock:
            self._cache.clear()
            if self._storage_path and self._storage_path.exists():
                try:
                    self._storage_path.unlink()
                except Exception:
                    pass
