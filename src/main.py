"""
Main entry point for the proxy caching server.

This script initializes and starts the proxy server listening on port 8888.
The proxy server accepts HTTP requests from clients and forwards them to
target web servers, relaying responses back to clients.
"""

import os

from proxy_server import ProxyServer
from admin_interface import AdminInterface
from logger import Logger


def main():
    """Entry point for the proxy server."""
    admin_interface = None
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
        blocked_ips = {
            "192.168.1.100",  # Example malicious IP
            "10.0.0.50",      # Example internal IP
            "104.20.23.154",  # example.com's resolved IP (for testing)
        }

        # Create and start proxy server on port 8888
        proxy = ProxyServer(
            host="0.0.0.0",
            port=8888,
            cache_ttl=60,
            cache_max_entries=100,
            blocked_hosts=blocked_hosts,
            blocked_keywords=blocked_keywords,
            blocked_ips=blocked_ips,
        )

        admin_password = os.environ.get("PROXY_ADMIN_PASSWORD", "admin")
        admin_interface = AdminInterface(
            proxy_server=proxy,
            host="127.0.0.1",
            port=8890,
            password=admin_password,
        )
        admin_interface.start()
        Logger.info("Admin credentials: user=admin, password from PROXY_ADMIN_PASSWORD")
        Logger.info("Admin URL: http://127.0.0.1:8890")

        proxy.start()

    except Exception as e:
        Logger.error(f"Fatal error: {str(e)}")
    finally:
        if admin_interface is not None:
            admin_interface.stop()


if __name__ == "__main__":
    main()
