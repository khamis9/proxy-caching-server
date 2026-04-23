"""
Level 3 cache validation script.

This script starts a local origin HTTP server, sends repeated GET requests
through the proxy, and verifies that the second response is served from cache.
"""

import argparse
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class CountingOriginHandler(BaseHTTPRequestHandler):
    """Origin server handler that tracks request count and simulates latency."""

    request_count = 0
    count_lock = threading.Lock()

    def do_GET(self):
        with CountingOriginHandler.count_lock:
            CountingOriginHandler.request_count += 1
            current_count = CountingOriginHandler.request_count

        # Add delay so cache speedup is easy to observe.
        time.sleep(0.25)

        body = f"origin-count={current_count}; path={self.path}".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Keep test output clean.
        return


def send_via_proxy(proxy_host: str, proxy_port: int, target_host: str, target_port: int, resource: str):
    """Send one GET request via proxy and return status, body, and elapsed time."""
    request = (
        f"GET {resource} HTTP/1.1\r\n"
        f"Host: {target_host}:{target_port}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )

    start = time.perf_counter()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(10)
        sock.connect((proxy_host, proxy_port))
        sock.sendall(request.encode("utf-8"))

        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
    finally:
        sock.close()

    elapsed = time.perf_counter() - start

    if b"\r\n\r\n" in response:
        headers, body = response.split(b"\r\n\r\n", 1)
    else:
        headers, body = response, b""

    status_line = headers.split(b"\r\n", 1)[0].decode("iso-8859-1", errors="ignore")
    return status_line, body.decode("utf-8", errors="ignore"), elapsed


def is_http_200(status_line: str) -> bool:
    """Return True when status line contains HTTP 200."""
    parts = status_line.split()
    return len(parts) >= 2 and parts[1] == "200"


def main() -> None:
    parser = argparse.ArgumentParser(description="Level 3 cache validation script")
    parser.add_argument("--proxy-host", default="127.0.0.1", help="Proxy host")
    parser.add_argument("--proxy-port", type=int, default=8888, help="Proxy port")
    parser.add_argument("--origin-host", default="127.0.0.1", help="Origin host")
    parser.add_argument("--origin-port", type=int, default=18080, help="Origin port")
    parser.add_argument("--resource", default="/cache-check", help="Resource path")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.origin_host, args.origin_port), CountingOriginHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    print("=" * 60)
    print("Level 3 Cache Validation")
    print("=" * 60)
    print(f"Origin server: {args.origin_host}:{args.origin_port}")
    print(f"Proxy server: {args.proxy_host}:{args.proxy_port}")
    print()

    try:
        status1, body1, t1 = send_via_proxy(
            args.proxy_host,
            args.proxy_port,
            args.origin_host,
            args.origin_port,
            args.resource,
        )
        status2, body2, t2 = send_via_proxy(
            args.proxy_host,
            args.proxy_port,
            args.origin_host,
            args.origin_port,
            args.resource,
        )

        with CountingOriginHandler.count_lock:
            origin_hits = CountingOriginHandler.request_count

        print(f"First response : {status1} | body='{body1}' | {t1:.3f}s")
        print(f"Second response: {status2} | body='{body2}' | {t2:.3f}s")
        print(f"Origin hit count: {origin_hits}")
        print()

        ok_status = is_http_200(status1) and is_http_200(status2)
        ok_body = body1 == body2
        ok_origin_hits = origin_hits == 1

        if ok_status and ok_body and ok_origin_hits:
            print("PASS: Level 3 cache behavior confirmed (cache hit on second request).")
            raise SystemExit(0)

        print("FAIL: Cache behavior not as expected.")
        if not ok_status:
            print("- One or both requests did not return HTTP 200")
        if not ok_body:
            print("- Response bodies differ (second request likely not served from cache)")
        if not ok_origin_hits:
            print("- Origin was hit more than once")
        raise SystemExit(1)

    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
