"""
Caching mechanisms and storage management.
"""

from collections import OrderedDict
from dataclasses import dataclass
import threading
import time
from typing import Optional, Tuple


@dataclass
class CacheEntry:
	"""Container for cached HTTP response data and cache metadata."""

	response_data: bytes
	created_at: float
	ttl_seconds: int


class ProxyCache:
	"""Thread-safe in-memory cache with TTL expiration and max-size eviction."""

	def __init__(self, ttl_seconds: int = 60, max_entries: int = 100):
		if ttl_seconds <= 0:
			raise ValueError("ttl_seconds must be greater than 0")
		if max_entries <= 0:
			raise ValueError("max_entries must be greater than 0")

		self.ttl_seconds = ttl_seconds
		self.max_entries = max_entries
		self._entries: "OrderedDict[str, CacheEntry]" = OrderedDict()
		self._lock = threading.Lock()
		self._hits = 0
		self._misses = 0
		self._evictions = 0

	def get(self, key: str) -> Optional[bytes]:
		"""Get a cached response by key if present and not expired."""
		if not key:
			return None

		now = time.time()
		with self._lock:
			self._remove_expired_unlocked(now)

			entry = self._entries.get(key)
			if entry is None:
				self._misses += 1
				return None

			# Move to end to retain recently used entries when evicting.
			self._entries.move_to_end(key)
			self._hits += 1
			return entry.response_data

	def set(self, key: str, response_data: bytes, ttl_seconds: Optional[int] = None) -> None:
		"""Store or update a cache entry, optionally overriding the default TTL."""
		if not key or not response_data:
			return

		effective_ttl = self.ttl_seconds if ttl_seconds is None else int(ttl_seconds)
		if effective_ttl <= 0:
			return

		now = time.time()
		with self._lock:
			self._remove_expired_unlocked(now)
			self._entries[key] = CacheEntry(
				response_data=response_data,
				created_at=now,
				ttl_seconds=effective_ttl,
			)
			self._entries.move_to_end(key)
			self._evict_if_needed_unlocked()

	def clear(self) -> None:
		"""Clear all cache entries and reset hit/miss counters."""
		with self._lock:
			self._entries.clear()
			self._hits = 0
			self._misses = 0

	def size(self) -> int:
		"""Return current number of entries after removing expired ones."""
		now = time.time()
		with self._lock:
			self._remove_expired_unlocked(now)
			return len(self._entries)

	def stats(self) -> Tuple[int, int, int, int]:
		"""Return cache hit/miss counts, evictions, and active entry count."""
		now = time.time()
		with self._lock:
			self._remove_expired_unlocked(now)
			return self._hits, self._misses, self._evictions, len(self._entries)

	def snapshot(self) -> list:
		"""Return a read-only snapshot of cache entries for admin visibility."""
		now = time.time()
		with self._lock:
			self._remove_expired_unlocked(now)
			items = []
			for key, entry in self._entries.items():
				age = max(0.0, now - entry.created_at)
				ttl_remaining = max(0.0, entry.ttl_seconds - age)
				items.append(
					{
						"key": key,
						"size_bytes": len(entry.response_data),
						"age_seconds": round(age, 3),
						"ttl_remaining_seconds": round(ttl_remaining, 3),
					}
				)
			return items

	def _remove_expired_unlocked(self, now: float) -> None:
		expired_keys = [
			key
			for key, entry in self._entries.items()
			if now - entry.created_at >= entry.ttl_seconds
		]
		for key in expired_keys:
			self._entries.pop(key, None)

	def _evict_if_needed_unlocked(self) -> None:
		while len(self._entries) > self.max_entries:
			self._entries.popitem(last=False)
			self._evictions += 1
