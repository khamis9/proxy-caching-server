"""
Handles client connections and requests.
Manages individual client-server-client communication flow.
"""

import socket
import select
import time
from typing import Optional, Tuple
from cache import ProxyCache
from filter import RequestFilter
from http_parser import HTTPParser
from logger import Logger


class ClientHandler:
    """Handles a single client connection."""

    # Configuration
    BUFFER_SIZE = 4096
    SOCKET_TIMEOUT = 10  # seconds

    def __init__(
        self,
        client_socket: socket.socket,
        client_address: Tuple,
        cache: Optional[ProxyCache] = None,
        request_filter: Optional[RequestFilter] = None,
    ):
        """
        Initialize client handler.
        
        Args:
            client_socket: Connected client socket
            client_address: Client address tuple (IP, port)
        """
        self.client_socket = client_socket
        self.client_address = client_address
        self.client_ip = client_address[0]
        self.client_port = client_address[1]
        self.cache = cache
        self.request_filter = request_filter

    def handle(self) -> None:
        """Handle a client connection and request."""
        request_start = time.perf_counter()
        try:
            # Log client connection
            Logger.info(f"Client connected: {self.client_ip}:{self.client_port}")

            # Receive request from client
            request_data = self._receive_request()
            if not request_data:
                self._send_error(400, "Bad Request", "Invalid or empty request")
                return

            Logger.info(f"Request received from {self.client_ip}:{self.client_port}")

            # Parse HTTP request
            parsed_request = HTTPParser.parse_request(request_data)
            if not parsed_request or not parsed_request.get("valid"):
                self._send_error(400, "Bad Request", "Failed to parse HTTP request")
                return

            # Log parsed request details
            host = parsed_request["host"]
            port = parsed_request["port"]
            resource = parsed_request["resource"]
            method = parsed_request["method"].upper()
            if method == "CONNECT":
                url = f"{host}:{port}"
            else:
                url = f"http://{host}:{port}{resource}"
            Logger.info(f"Requested URL: {url}")

            if self.request_filter:
                blocked, reason = self.request_filter.is_blocked(host=host, resource=resource)
                if blocked:
                    Logger.warning(
                        f"Blocked request from {self.client_ip}:{self.client_port} to {url} ({reason})"
                    )
                    self._send_error(
                        403,
                        "Forbidden",
                        f"Request blocked by proxy policy. Reason: {reason}",
                    )
                    return

            if method == "CONNECT":
                Logger.info(f"Request forwarded to {host}:{port} (CONNECT tunnel)")
                tunnel_ok = self._handle_connect_tunnel(host, port)
                if not tunnel_ok:
                    self._send_error(502, "Bad Gateway", "Failed to establish HTTPS tunnel")
                    return

                Logger.info(f"Response received from {host}:{port} (CONNECT tunnel closed)")
                Logger.info(f"Response sent to {self.client_ip}:{self.client_port}")
                elapsed_ms = (time.perf_counter() - request_start) * 1000
                Logger.info(f"Request completed in {elapsed_ms:.2f} ms (source=tunnel)")
                return

            cache_key = self._build_cache_key(parsed_request)
            if method == "GET" and self.cache:
                cached_response = self.cache.get(cache_key)
                if cached_response is not None:
                    Logger.info(f"Cache hit: {cache_key}")
                    Logger.info(f"Response received from cache for {host}:{port}")
                    self._send_response(cached_response)
                    Logger.info(f"Response sent to {self.client_ip}:{self.client_port}")
                    elapsed_ms = (time.perf_counter() - request_start) * 1000
                    Logger.info(f"Request completed in {elapsed_ms:.2f} ms (source=cache)")
                    return

                Logger.info(f"Cache miss: {cache_key}")

            # Forward request to target server
            response_data = self._forward_request(parsed_request)
            if not response_data:
                self._send_error(502, "Bad Gateway", "Failed to connect to target server")
                return

            Logger.info(f"Response received from {host}:{port}")

            if method == "GET" and self.cache and self._is_cacheable_response(response_data):
                header_ttl = HTTPParser.get_cache_ttl(response_data)
                if header_ttl == 0:
                    Logger.info(f"Response not cached due to cache policy headers: {cache_key}")
                elif header_ttl is None:
                    self.cache.set(cache_key, response_data)
                    Logger.info(f"Cached response: {cache_key} (ttl={self.cache.ttl_seconds}s)")
                else:
                    self.cache.set(cache_key, response_data, ttl_seconds=header_ttl)
                    Logger.info(f"Cached response: {cache_key} (ttl={header_ttl}s from headers)")

            # Send response to client
            self._send_response(response_data)

            # Log response sent
            Logger.info(f"Response sent to {self.client_ip}:{self.client_port}")
            elapsed_ms = (time.perf_counter() - request_start) * 1000
            Logger.info(f"Request completed in {elapsed_ms:.2f} ms (source=origin)")

        except Exception as e:
            Logger.error(f"Error handling client {self.client_ip}:{self.client_port}: {str(e)}")
            try:
                self._send_error(500, "Internal Server Error", "An unexpected error occurred")
            except:
                pass
        finally:
            self.client_socket.close()
            Logger.info(f"Client disconnected: {self.client_ip}:{self.client_port}")

    @staticmethod
    def _build_cache_key(parsed_request: dict) -> str:
        """Build a stable cache key for GET request caching."""
        method = parsed_request["method"].upper()
        host = parsed_request["host"]
        port = parsed_request["port"]
        resource = parsed_request["resource"]
        return f"{method}:{host}:{port}{resource}"

    @staticmethod
    def _is_cacheable_response(response_data: bytes) -> bool:
        """Cache successful responses only."""
        status_code = HTTPParser.get_response_status_code(response_data)
        return status_code == 200

    def _handle_connect_tunnel(self, host: str, port: int) -> bool:
        """Forward encrypted HTTPS traffic transparently using CONNECT."""
        target_socket = None
        try:
            target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target_socket.settimeout(self.SOCKET_TIMEOUT)
            target_socket.connect((host, port))

            self.client_socket.sendall(
                b"HTTP/1.1 200 Connection Established\r\n"
                b"Proxy-Agent: PythonProxy/1.0\r\n"
                b"\r\n"
            )

            self.client_socket.settimeout(None)
            target_socket.settimeout(None)

            sockets = [self.client_socket, target_socket]
            while True:
                readable, _, exceptional = select.select(sockets, [], sockets, self.SOCKET_TIMEOUT)

                if exceptional:
                    return False

                if not readable:
                    # Close idle tunnels after timeout window.
                    return True

                for source in readable:
                    data = source.recv(self.BUFFER_SIZE)
                    if not data:
                        return True

                    destination = target_socket if source is self.client_socket else self.client_socket
                    destination.sendall(data)

        except socket.timeout:
            Logger.error(f"Timeout while tunneling CONNECT to {host}:{port}")
            return False
        except Exception as e:
            Logger.error(f"Error in CONNECT tunnel to {host}:{port}: {str(e)}")
            return False
        finally:
            if target_socket:
                target_socket.close()

    def _receive_request(self) -> str:
        """
        Receive HTTP request from client.
        
        Returns:
            Request data as string, or empty string if error
        """
        try:
            self.client_socket.settimeout(self.SOCKET_TIMEOUT)
            request_data = b""

            while True:
                chunk = self.client_socket.recv(self.BUFFER_SIZE)
                if not chunk:
                    break
                request_data += chunk

                # Check if we have received complete headers (end with \r\n\r\n)
                if b"\r\n\r\n" in request_data:
                    break

            return request_data.decode("utf-8", errors="ignore")
        except socket.timeout:
            Logger.error("Timeout waiting for client request")
            return ""
        except Exception as e:
            Logger.error(f"Error receiving request: {str(e)}")
            return ""

    def _forward_request(self, parsed_request: dict) -> bytes:
        """
        Forward HTTP request to target server.
        
        Args:
            parsed_request: Parsed HTTP request dictionary
            
        Returns:
            Response data from target server, or empty bytes if error
        """
        target_socket = None
        try:
            host = parsed_request["host"]
            port = parsed_request["port"]
            method = parsed_request["method"]
            resource = parsed_request["resource"]
            headers = parsed_request["headers"]

            # Log forwarding
            Logger.info(f"Forwarding request to {host}:{port}")

            # Create socket and connect to target server
            target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target_socket.settimeout(self.SOCKET_TIMEOUT)
            target_socket.connect((host, port))

            # Build request for target server
            forward_request = HTTPParser.build_request(method, resource, host, headers)

            # Send request to target server
            target_socket.sendall(forward_request.encode("utf-8"))

            # Receive response from target server
            response_data = b""
            while True:
                chunk = target_socket.recv(self.BUFFER_SIZE)
                if not chunk:
                    break
                response_data += chunk

            return response_data

        except socket.timeout:
            Logger.error(f"Timeout connecting to target server {host}:{port}")
            return b""
        except socket.error as e:
            Logger.error(f"Socket error connecting to {host}:{port}: {str(e)}")
            return b""
        except Exception as e:
            Logger.error(f"Error forwarding request: {str(e)}")
            return b""
        finally:
            if target_socket:
                target_socket.close()

    def _send_response(self, response_data: bytes) -> None:
        """
        Send response to client.
        
        Args:
            response_data: Response bytes to send
        """
        try:
            self.client_socket.sendall(response_data)
        except Exception as e:
            Logger.error(f"Error sending response to client: {str(e)}")

    def _send_error(self, status_code: int, status_text: str, message: str) -> None:
        """
        Send error response to client.
        
        Args:
            status_code: HTTP status code
            status_text: HTTP status text
            message: Error message body
        """
        try:
            error_response = (
                f"HTTP/1.1 {status_code} {status_text}\r\n"
                f"Content-Type: text/html\r\n"
                f"Connection: close\r\n"
                f"\r\n"
                f"<html><body><h1>{status_code} {status_text}</h1>"
                f"<p>{message}</p></body></html>"
            )
            self.client_socket.sendall(error_response.encode("utf-8"))
            Logger.info(f"Error response sent: {status_code} {status_text}")
        except Exception as e:
            Logger.error(f"Error sending error response: {str(e)}")
