"""Dead-letter queue (DLQ) for failed, unparseable, or schema-invalid ingestion envelopes."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from typing import Dict, List, Optional
import uuid

from piis.integrations.contracts import DeadLetterItem, IngestionEnvelope


class DeadLetterQueue:
    """Thread-safe queue recording failed ingestion events for forensic inspection and retry.
    
    Supports restart persistence via append-only/snapshot JSONL file storage.
    """

    MAX_REPLAY_ATTEMPTS: int = 3

    def __init__(
        self,
        max_items: int = 1000,
        storage_path: Optional[Path | str] = None,
    ):
        self.max_items = max_items
        self._lock = threading.RLock()
        self._storage_path: Optional[Path] = Path(storage_path) if storage_path else None
        self._items: Dict[str, DeadLetterItem] = {}

        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_from_storage()

    def _load_from_storage(self) -> None:
        """Load dead letter records from storage on startup."""
        if not self._storage_path or not self._storage_path.exists():
            return

        try:
            with self._storage_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        item = DeadLetterItem.from_dict(data)
                        self._items[item.item_id] = item
                    except Exception:
                        continue
        except Exception:
            pass

    def _persist_snapshot(self) -> None:
        """Atomically persist current items to storage."""
        if not self._storage_path:
            return
        try:
            temp_file = self._storage_path.with_suffix(".tmp")
            with temp_file.open("w", encoding="utf-8") as f:
                for item in self._items.values():
                    line = json.dumps(item.to_dict())
                    f.write(line + "\n")
            temp_file.replace(self._storage_path)
        except Exception:
            pass

    def push(
        self,
        envelope: IngestionEnvelope,
        reason: str,
        error_details: str,
    ) -> DeadLetterItem:
        """Record a failed ingestion envelope."""
        with self._lock:
            # Check if this envelope is already in DLQ for retry counting
            existing_id = None
            for item_id, item in self._items.items():
                if item.envelope.envelope_id == envelope.envelope_id:
                    existing_id = item_id
                    break

            now_str = datetime.now(timezone.utc).isoformat()
            if existing_id:
                item = self._items[existing_id]
                item.attempt_count += 1
                item.last_failed_at = now_str
                item.failure_reason = reason
                item.error_details = error_details
                if item.attempt_count > self.MAX_REPLAY_ATTEMPTS:
                    item.replay_status = "PERMANENTLY_FAILED"
                else:
                    item.replay_status = "FAILED"
                self._persist_snapshot()
                return item

            # Create new DLQ item
            dlq_id = f"DLQ-{uuid.uuid4().hex[:10].upper()}"
            item = DeadLetterItem(
                item_id=dlq_id,
                envelope=envelope,
                failure_reason=reason,
                error_details=error_details,
                attempt_count=1,
                first_failed_at=now_str,
                last_failed_at=now_str,
                replay_status="PENDING",
            )

            # Evict oldest if exceeding capacity
            if len(self._items) >= self.max_items:
                oldest_key = min(self._items.keys(), key=lambda k: self._items[k].first_failed_at)
                del self._items[oldest_key]

            self._items[dlq_id] = item
            self._persist_snapshot()
            return item

    def get(self, item_id: str) -> Optional[DeadLetterItem]:
        """Retrieve a specific DLQ item."""
        with self._lock:
            return self._items.get(item_id)

    def list_items(self, limit: int = 50, offset: int = 0) -> List[DeadLetterItem]:
        """List dead-letter items sorted by most recent failure."""
        with self._lock:
            sorted_items = sorted(
                self._items.values(),
                key=lambda x: x.last_failed_at,
                reverse=True,
            )
            return sorted_items[offset : offset + limit]

    def count(self) -> int:
        """Return total DLQ items currently stored."""
        with self._lock:
            return len(self._items)

    def update_status(self, item_id: str, status: str, error: Optional[str] = None) -> Optional[DeadLetterItem]:
        """Update replay status and error notes for an item."""
        with self._lock:
            item = self._items.get(item_id)
            if item:
                item.replay_status = status
                item.last_failed_at = datetime.now(timezone.utc).isoformat()
                if error:
                    item.error_details = error
                self._persist_snapshot()
                return item
            return None

    def remove(self, item_id: str) -> bool:
        """Remove an item after successful re-ingestion or operator dismissal."""
        with self._lock:
            if item_id in self._items:
                del self._items[item_id]
                self._persist_snapshot()
                return True
            return False

    def clear(self) -> None:
        """Clear all DLQ items."""
        with self._lock:
            self._items.clear()
            if self._storage_path and self._storage_path.exists():
                try:
                    self._storage_path.unlink()
                except Exception:
                    pass
