"""
Test client for proxy server.
Sends HTTP GET requests to the proxy and displays responses.
"""

import socket
import sys


def test_proxy(target_url: str = "http://www.example.com/", proxy_host: str = "127.0.0.1", proxy_port: int = 8888):
    """
    Send a test request through the proxy.
    
    Args:
        target_url: URL to request through proxy
        proxy_host: Proxy server host
        proxy_port: Proxy server port
    """
    try:
        # Parse target URL
        if target_url.startswith("http://"):
            target_url = target_url[7:]
        
        if "/" in target_url:
            host, resource = target_url.split("/", 1)
            resource = "/" + resource
        else:
            host = target_url
            resource = "/"

        # Create socket to proxy
        print(f"[CLIENT] Connecting to proxy {proxy_host}:{proxy_port}")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((proxy_host, proxy_port))
        print(f"[CLIENT] Connected to proxy")

        # Build HTTP request
        request = (
            f"GET {resource} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        )

        print(f"[CLIENT] Sending request:")
        print(request)

        # Send request
        sock.sendall(request.encode("utf-8"))
        print(f"[CLIENT] Request sent")

        # Receive response
        print(f"[CLIENT] Waiting for response...")
        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk

        sock.close()

        print(f"[CLIENT] Response received ({len(response)} bytes):")
        print(response.decode("utf-8", errors="ignore"))

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    print("=" * 60)
    print("Proxy Server Test Client")
    print("=" * 60)
    test_proxy("http://www.example.com/")
