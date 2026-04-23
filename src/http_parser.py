"""
HTTP request/response parsing utilities.
Parses HTTP GET requests to extract method, host, port, and resource.
"""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Optional
from logger import Logger


class HTTPParser:
    """Parser for HTTP requests and responses."""

    @staticmethod
    def parse_request(request_data: str) -> Optional[Dict]:
        """
        Parse HTTP request.
        
        Args:
            request_data: Raw HTTP request data
            
        Returns:
            Dictionary with method, host, port, resource, headers, or None if invalid
        """
        try:
            lines = request_data.split('\r\n')
            if not lines:
                return None

            # Parse request line (e.g., "GET /index.html HTTP/1.1")
            request_line = lines[0].split()
            if len(request_line) < 3:
                Logger.error(f"Invalid request line: {lines[0]}")
                return None

            method = request_line[0].upper()
            url = request_line[1]
            http_version = request_line[2]

            # Support GET and CONNECT methods.
            if method not in {"GET", "CONNECT"}:
                Logger.warning(f"Unsupported HTTP method: {method}")
                return None

            # Parse headers
            headers = {}
            for i in range(1, len(lines)):
                if lines[i] == "":
                    break
                if ":" in lines[i]:
                    key, value = lines[i].split(":", 1)
                    headers[key.strip()] = value.strip()

            host = ""
            port = 80
            resource = "/"

            if method == "CONNECT":
                # CONNECT request line target is typically "host:port"
                if ":" not in url:
                    Logger.error(f"Invalid CONNECT target: {url}")
                    return None

                host, port_str = url.rsplit(":", 1)
                try:
                    port = int(port_str)
                except ValueError:
                    Logger.error(f"Invalid CONNECT port: {port_str}")
                    return None

                if not host:
                    Logger.error("CONNECT host is empty")
                    return None

                resource = "/"

            else:
                # Extract host and port from Host header for GET
                host_header = headers.get("Host", "")
                if not host_header:
                    Logger.error("Missing Host header")
                    return None

                if ":" in host_header:
                    host, port_str = host_header.rsplit(":", 1)
                    try:
                        port = int(port_str)
                    except ValueError:
                        port = 80
                else:
                    host = host_header
                    port = 80

                # Extract resource from URL
                if url.startswith("http://"):
                    resource_part = url[7:]
                    if "/" in resource_part:
                        resource = "/" + resource_part.split("/", 1)[1]
                    else:
                        resource = "/"
                elif url.startswith("https://"):
                    Logger.warning("Use CONNECT for HTTPS tunneling")
                    return None
                else:
                    resource = url if url.startswith("/") else "/" + url

            return {
                "method": method,
                "host": host,
                "port": port,
                "resource": resource,
                "headers": headers,
                "http_version": http_version,
                "valid": True
            }

        except Exception as e:
            Logger.error(f"Error parsing request: {str(e)}")
            return None

    @staticmethod
    def parse_response_headers(response_data: bytes) -> Dict[str, str]:
        """Parse response headers from raw HTTP response bytes."""
        if not response_data:
            return {}

        header_bytes = response_data.split(b"\r\n\r\n", 1)[0]
        header_text = header_bytes.decode("iso-8859-1", errors="ignore")
        lines = header_text.split("\r\n")
        headers = {}

        for line in lines[1:]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()

        return headers

    @staticmethod
    def get_response_status_code(response_data: bytes) -> Optional[int]:
        """Return HTTP status code from raw HTTP response bytes."""
        if not response_data:
            return None

        status_line = response_data.split(b"\r\n", 1)[0].decode("iso-8859-1", errors="ignore")
        parts = status_line.split()
        if len(parts) < 2:
            return None

        try:
            return int(parts[1])
        except ValueError:
            return None

    @staticmethod
    def get_cache_ttl(response_data: bytes) -> Optional[int]:
        """Derive cache TTL from response headers. Returns None when unknown."""
        headers = HTTPParser.parse_response_headers(response_data)
        cache_control = headers.get("cache-control", "").lower()
        directives = [item.strip() for item in cache_control.split(",") if item.strip()]

        if "no-store" in directives:
            return 0

        for directive in directives:
            if directive.startswith("max-age="):
                try:
                    max_age = int(directive.split("=", 1)[1])
                    return max(0, max_age)
                except ValueError:
                    pass

        expires_value = headers.get("expires")
        if expires_value:
            try:
                expires_dt = parsedate_to_datetime(expires_value)
                if expires_dt.tzinfo is None:
                    expires_dt = expires_dt.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                ttl = int((expires_dt - now).total_seconds())
                return max(0, ttl)
            except Exception:
                return None

        return None

    @staticmethod
    def build_request(method: str, resource: str, host: str, headers: Dict) -> str:
        """
        Build HTTP request to forward to target server.
        
        Args:
            method: HTTP method
            resource: Requested resource
            host: Target host
            headers: HTTP headers
            
        Returns:
            Formatted HTTP request string
        """
        # Build request line
        request_line = f"{method} {resource} HTTP/1.1\r\n"

        # Build headers
        header_lines = request_line
        header_lines += f"Host: {host}\r\n"

        # Add other headers (skip certain ones that shouldn't be forwarded)
        skip_headers = {"Host", "Connection", "Proxy-Connection"}
        for key, value in headers.items():
            if key not in skip_headers:
                header_lines += f"{key}: {value}\r\n"

        # Add connection close header for Level 1
        header_lines += "Connection: close\r\n"
        header_lines += "\r\n"

        return header_lines
