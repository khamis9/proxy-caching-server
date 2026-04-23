"""
Request filtering and validation.
"""

import socket
from typing import Iterable, Optional, Tuple


class RequestFilter:
	"""Simple blacklist-based request filter for proxy traffic."""

	def __init__(
		self,
		blocked_hosts: Optional[Iterable[str]] = None,
		blocked_keywords: Optional[Iterable[str]] = None,
		blocked_ips: Optional[Iterable[str]] = None,
	):
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

		if self._is_host_blocked(normalized_host):
			return True, f"Host '{normalized_host}' is blacklisted"

		for keyword in self.blocked_keywords:
			if keyword in full_url:
				return True, f"URL matched blocked keyword '{keyword}'"

		resolved_ip = self._resolve_host_ip(normalized_host)
		if resolved_ip and resolved_ip in self.blocked_ips:
			return True, f"Destination IP '{resolved_ip}' is blacklisted"

		return False, ""

	def _is_host_blocked(self, host: str) -> bool:
		if not host:
			return False

		for blocked_host in self.blocked_hosts:
			if host == blocked_host or host.endswith(f".{blocked_host}"):
				return True
		return False

	@staticmethod
	def _resolve_host_ip(host: str) -> Optional[str]:
		if not host:
			return None
		try:
			return socket.gethostbyname(host)
		except Exception:
			return None
