"""
Request filtering and validation.
"""

import socket
import threading
from typing import Iterable, Optional, Tuple


class RequestFilter:
	"""Simple blacklist-based request filter for proxy traffic."""

	def __init__(
		self,
		blocked_hosts: Optional[Iterable[str]] = None,
		blocked_keywords: Optional[Iterable[str]] = None,
		blocked_ips: Optional[Iterable[str]] = None,
	):
		self._lock = threading.Lock()
		self.blocked_hosts = {
			host.strip().lower() for host in (blocked_hosts or []) if host and host.strip()
		}
		self.blocked_keywords = {
			keyword.strip().lower()
			for keyword in (blocked_keywords or [])
			if keyword and keyword.strip()
		}
		self.blocked_ips = {
			ip.strip() for ip in (blocked_ips or []) if ip and ip.strip()
		}

	def is_blocked(self, host: str, resource: str) -> Tuple[bool, str]:
		"""Return whether the request should be blocked and the reason."""
		normalized_host = (host or "").strip().lower()
		normalized_resource = (resource or "/").strip()
		full_url = f"{normalized_host}{normalized_resource}".lower()

		with self._lock:
			blocked_hosts = set(self.blocked_hosts)
			blocked_keywords = set(self.blocked_keywords)
			blocked_ips = set(self.blocked_ips)

		# Debug logging
		from logger import Logger
		Logger.info(f"[FILTER] Host: {normalized_host}, Blocked IPs: {blocked_ips}")

		if self._is_host_blocked(normalized_host, blocked_hosts):
			return True, f"Host '{normalized_host}' is blacklisted"

		for keyword in blocked_keywords:
			if keyword in full_url:
				return True, f"URL matched blocked keyword '{keyword}'"

		resolved_ip = self._resolve_host_ip(normalized_host)
		Logger.info(f"[FILTER] Resolved {normalized_host} -> {resolved_ip}")
		if resolved_ip and resolved_ip in blocked_ips:
			Logger.info(f"[FILTER] IP {resolved_ip} is in blocked list!")
			return True, f"Destination IP '{resolved_ip}' is blacklisted"

		return False, ""

	def _is_host_blocked(self, host: str, blocked_hosts: set) -> bool:
		if not host:
			return False

		for blocked_host in blocked_hosts:
			if host == blocked_host or host.endswith(f".{blocked_host}"):
				return True
		return False

	def snapshot(self) -> dict:
		"""Return a read-only snapshot of active blacklist values."""
		with self._lock:
			return {
				"hosts": sorted(self.blocked_hosts),
				"keywords": sorted(self.blocked_keywords),
				"ips": sorted(self.blocked_ips),
			}

	def add_host(self, host: str) -> bool:
		"""Add a blocked host/domain. Returns True when added."""
		normalized = (host or "").strip().lower()
		if not normalized:
			return False
		with self._lock:
			if normalized in self.blocked_hosts:
				return False
			self.blocked_hosts.add(normalized)
			return True

	def add_keyword(self, keyword: str) -> bool:
		"""Add a blocked URL keyword. Returns True when added."""
		normalized = (keyword or "").strip().lower()
		if not normalized:
			return False
		with self._lock:
			if normalized in self.blocked_keywords:
				return False
			self.blocked_keywords.add(normalized)
			return True

	def add_ip(self, ip: str) -> bool:
		"""Add a blocked destination IP. Returns True when added."""
		normalized = (ip or "").strip()
		if not normalized:
			return False
		with self._lock:
			if normalized in self.blocked_ips:
				return False
			self.blocked_ips.add(normalized)
			return True

	def remove_host(self, host: str) -> bool:
		"""Remove blocked host/domain. Returns True when removed."""
		normalized = (host or "").strip().lower()
		if not normalized:
			return False
		with self._lock:
			if normalized not in self.blocked_hosts:
				return False
			self.blocked_hosts.remove(normalized)
			return True

	def remove_keyword(self, keyword: str) -> bool:
		"""Remove blocked keyword. Returns True when removed."""
		normalized = (keyword or "").strip().lower()
		if not normalized:
			return False
		with self._lock:
			if normalized not in self.blocked_keywords:
				return False
			self.blocked_keywords.remove(normalized)
			return True

	def remove_ip(self, ip: str) -> bool:
		"""Remove blocked IP. Returns True when removed."""
		normalized = (ip or "").strip()
		if not normalized:
			return False
		with self._lock:
			if normalized not in self.blocked_ips:
				return False
			self.blocked_ips.remove(normalized)
			return True

	@staticmethod
	def _resolve_host_ip(host: str) -> Optional[str]:
		if not host:
			return None
		try:
			return socket.gethostbyname(host)
		except Exception:
			return None
