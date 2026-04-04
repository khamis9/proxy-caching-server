"""
HTTP request/response parsing utilities.
Parses HTTP GET requests to extract method, host, port, and resource.
"""

from typing import Tuple, Dict, Optional
from logger import Logger


class HTTPParser:
    """Parser for HTTP requests and responses."""

    @staticmethod
    def parse_request(request_data: str) -> Optional[Dict]:
        """
        Parse HTTP GET request.
        
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

            method = request_line[0]
            url = request_line[1]
            http_version = request_line[2]

            # Only support GET for Level 1
            if method.upper() != "GET":
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

            # Extract host and port from Host header
            host_header = headers.get("Host", "")
            if not host_header:
                Logger.error("Missing Host header")
                return None

            # Parse Host header (e.g., "example.com:8080" or "example.com")
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
                # Absolute URL
                resource_part = url[7:]  # Remove "http://"
                if "/" in resource_part:
                    resource = "/" + resource_part.split("/", 1)[1]
                else:
                    resource = "/"
            elif url.startswith("https://"):
                Logger.warning("HTTPS not supported in Level 1")
                return None
            else:
                # Relative URL
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
