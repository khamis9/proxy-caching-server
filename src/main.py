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
        Logger.configure(log_file_path="logs/proxy_server.log")

        Logger.info("=" * 60)
        Logger.info("Proxy Caching Server - Level 5 Advanced Features")
        Logger.info("=" * 60)
        
        blocked_hosts = {
            "blocked.test",
            "ads.example",
        }
        blocked_keywords = {
            "forbidden",
            "malware",
        }

        # Create and start proxy server on port 8888
        proxy = ProxyServer(
            host="0.0.0.0",
            port=8888,
            cache_ttl=60,
            cache_max_entries=100,
            blocked_hosts=blocked_hosts,
            blocked_keywords=blocked_keywords,
        )
        proxy.start()

    except Exception as e:
        Logger.error(f"Fatal error: {str(e)}")


if __name__ == "__main__":
    main()
