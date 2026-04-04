"""
Core proxy server implementation.
Implements a basic HTTP proxy server that listens for client connections,
forwards requests to target servers, and relays responses back.
"""

import socket
from client_handler import ClientHandler
from logger import Logger


class ProxyServer:
    """
    Basic HTTP proxy server.
    
    Listens on a specified port, accepts client connections,
    and forwards HTTP requests to target servers.
    """

    def __init__(self, host: str = "localhost", port: int = 8888):
        """
        Initialize proxy server.
        
        Args:
            host: Host to bind to
            port: Port to listen on
        """
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False

    def start(self) -> None:
        """Start the proxy server."""
        try:
            # Create server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Bind to host and port
            self.server_socket.bind((self.host, self.port))

            # Listen for connections
            self.server_socket.listen(1)

            Logger.info(f"Proxy server started on {self.host}:{self.port}")
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
        For Level 1, this handles one client at a time sequentially.
        """
        while self.running:
            try:
                # Accept client connection
                client_socket, client_address = self.server_socket.accept()

                # Handle client request
                handler = ClientHandler(client_socket, client_address)
                handler.handle()

                # For Level 1, we handle one client at a time
                # In Level 2, this will be replaced with threading

            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                Logger.error(f"Error accepting connection: {str(e)}")

    def stop(self) -> None:
        """Stop the proxy server."""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
                Logger.info("Proxy server stopped")
            except Exception as e:
                Logger.error(f"Error closing server socket: {str(e)}")
