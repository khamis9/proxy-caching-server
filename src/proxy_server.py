"""
Core proxy server implementation.
Implements a basic HTTP proxy server that listens for client connections,
forwards requests to target servers, and relays responses back.
"""

import socket
import threading
from typing import Iterable, Optional
from cache import ProxyCache
from client_handler import ClientHandler
from filter import RequestFilter
from logger import Logger


class ProxyServer:
    """
    Basic HTTP proxy server.
    
    Listens on a specified port, accepts client connections,
    and forwards HTTP requests to target servers.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8888,
        cache_ttl: int = 60,
        cache_max_entries: int = 100,
        blocked_hosts: Optional[Iterable[str]] = None,
        blocked_keywords: Optional[Iterable[str]] = None,
        blocked_ips: Optional[Iterable[str]] = None,
    ):
        """
        Initialize proxy server.
        
        Args:
            host: Host to bind to
            port: Port to listen on
            cache_ttl: Cache timeout in seconds
            cache_max_entries: Maximum number of cache entries
            blocked_hosts: Hostnames/domains denied by the proxy
            blocked_keywords: URL keywords denied by the proxy
            blocked_ips: Destination IP addresses denied by the proxy
        """
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.client_threads = []
        self.threads_lock = threading.Lock()
        self.cache = ProxyCache(ttl_seconds=cache_ttl, max_entries=cache_max_entries)
        self.request_filter = RequestFilter(
            blocked_hosts=blocked_hosts,
            blocked_keywords=blocked_keywords,
            blocked_ips=blocked_ips,
        )

    def start(self) -> None:
        """Start the proxy server."""
        try:
            # Create server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Bind to host and port
            self.server_socket.bind((self.host, self.port))

            # Listen for multiple pending connections (Level 2)
            self.server_socket.listen(50)
            self.server_socket.settimeout(1.0)

            Logger.info(f"Proxy server started on {self.host}:{self.port}")
            Logger.info(
                f"Cache enabled: ttl={self.cache.ttl_seconds}s, max_entries={self.cache.max_entries}"
            )
            Logger.info(
                "Filtering enabled: "
                f"hosts={len(self.request_filter.blocked_hosts)}, "
                f"keywords={len(self.request_filter.blocked_keywords)}, "
                f"ips={len(self.request_filter.blocked_ips)}"
            )
            self.running = True

            # Accept connections
            self._accept_connections()

        except socket.error as e:
            Logger.error(f"Socket error: {str(e)}")
        except KeyboardInterrupt:
            Logger.info("Proxy server interrupted by user")
        except Exception as e:
            Logger.error(f"Unexpected error: {str(e)}")
        finally:
            self.stop()

    def _accept_connections(self) -> None:
        """
        Accept and handle client connections.
        For Level 2, each client is handled in a dedicated thread.
        """
        while self.running:
            try:
                # Accept client connection
                client_socket, client_address = self.server_socket.accept()

                # Handle each client in a separate thread
                thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_address),
                    daemon=True,
                )
                with self.threads_lock:
                    self.client_threads.append(thread)

                thread.start()

            except KeyboardInterrupt:
                self.running = False
            except socket.timeout:
                continue
            except OSError as e:
                if not self.running:
                    break
                Logger.error(f"Socket error while accepting connection: {str(e)}")
            except Exception as e:
                Logger.error(f"Error accepting connection: {str(e)}")

    def _handle_client(self, client_socket: socket.socket, client_address: tuple) -> None:
        """Handle a single client connection in a worker thread."""
        try:
            handler = ClientHandler(
                client_socket,
                client_address,
                cache=self.cache,
                request_filter=self.request_filter,
            )
            handler.handle()
        finally:
            current_thread = threading.current_thread()
            with self.threads_lock:
                self.client_threads = [
                    thread for thread in self.client_threads if thread is not current_thread
                ]

    def stop(self) -> None:
        """Stop the proxy server."""
        self.running = False

        hits, misses, evictions, active_entries = self.cache.stats()
        Logger.info(
            "Cache stats: "
            f"hits={hits}, misses={misses}, evictions={evictions}, active_entries={active_entries}"
        )

        if self.server_socket:
            try:
                self.server_socket.close()
                self.server_socket = None
                Logger.info("Proxy server stopped")
            except Exception as e:
                Logger.error(f"Error closing server socket: {str(e)}")

        with self.threads_lock:
            threads = list(self.client_threads)

        for thread in threads:
            thread.join(timeout=2.0)
