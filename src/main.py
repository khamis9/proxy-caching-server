"""
Main entry point for the proxy caching server.

This script initializes and starts the proxy server listening on port 8888.
The proxy server accepts HTTP requests from clients and forwards them to
target web servers, relaying responses back to clients.
"""

from proxy_server import ProxyServer
from logger import Logger


def main():
    """Entry point for the proxy server."""
    try:
        Logger.info("=" * 60)
        Logger.info("Proxy Caching Server - Level 1 Basic Proxy")
        Logger.info("=" * 60)
        
        # Create and start proxy server on port 8888
        proxy = ProxyServer(host="0.0.0.0", port=8888)
        proxy.start()

    except Exception as e:
        Logger.error(f"Fatal error: {str(e)}")


if __name__ == "__main__":
    main()
