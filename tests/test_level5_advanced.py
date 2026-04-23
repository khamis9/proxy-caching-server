"""
Level 5 advanced validation script.

Validates:
1) Smart caching via Cache-Control max-age.
2) Performance gain from cache hits.
3) HTTPS CONNECT tunneling behavior (raw tunnel test).
"""

import argparse
import socket
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class SmartCacheOriginHandler(BaseHTTPRequestHandler):
    """Origin server with cache headers and request counter."""

    request_count = 0
    count_lock = threading.Lock()

    def do_GET(self):
        with SmartCacheOriginHandler.count_lock:
            SmartCacheOriginHandler.request_count += 1
            current_count = SmartCacheOriginHandler.request_count

        # Artificial delay to make cache speedup measurable.
        time.sleep(0.30)

        body = f"smart-count={current_count}; path={self.path}".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=2")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class EchoTCPHandler(socketserver.BaseRequestHandler):
    """Echo server used to validate CONNECT tunnel byte forwarding."""

    def handle(self):
        while True:
            data = self.request.recv(4096)
            if not data:
                return
            self.request.sendall(data)


def send_get_via_proxy(proxy_host: str, proxy_port: int, target_host: str, target_port: int, resource: str):
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


def has_status_code(status_line: str, status_code: int) -> bool:
    """Return True when status line contains the expected HTTP status code."""
    parts = status_line.split()
    return len(parts) >= 2 and parts[1] == str(status_code)


def read_until_double_crlf(sock: socket.socket) -> bytes:
    """Read from socket until HTTP headers are complete."""
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


def test_connect_tunnel(proxy_host: str, proxy_port: int, target_host: str, target_port: int):
    """Validate CONNECT by tunneling to a local echo server."""
    payload = b"hello-through-connect"

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(10)
        sock.connect((proxy_host, proxy_port))

        connect_request = (
            f"CONNECT {target_host}:{target_port} HTTP/1.1\r\n"
            f"Host: {target_host}:{target_port}\r\n"
            "Proxy-Connection: keep-alive\r\n"
            "\r\n"
        )
        sock.sendall(connect_request.encode("utf-8"))

        response_headers = read_until_double_crlf(sock)
        status_line = response_headers.split(b"\r\n", 1)[0].decode("iso-8859-1", errors="ignore")

        if not status_line.startswith("HTTP/1.1 200"):
            return False, status_line

        sock.sendall(payload)
        echoed = sock.recv(len(payload))
        return echoed == payload, status_line

    finally:
        sock.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Level 5 advanced feature validation")
    parser.add_argument("--proxy-host", default="127.0.0.1", help="Proxy host")
    parser.add_argument("--proxy-port", type=int, default=8888, help="Proxy port")
    parser.add_argument("--origin-host", default="127.0.0.1", help="Origin host")
    parser.add_argument("--origin-port", type=int, default=18082, help="Origin port")
    parser.add_argument("--echo-host", default="127.0.0.1", help="Echo host for CONNECT")
    parser.add_argument("--echo-port", type=int, default=19090, help="Echo port for CONNECT")
    parser.add_argument("--resource", default="/level5-check", help="Resource path")
    args = parser.parse_args()

    origin_server = ThreadingHTTPServer((args.origin_host, args.origin_port), SmartCacheOriginHandler)
    origin_thread = threading.Thread(target=origin_server.serve_forever, daemon=True)
    origin_thread.start()

    echo_server = socketserver.ThreadingTCPServer((args.echo_host, args.echo_port), EchoTCPHandler)
    echo_server.daemon_threads = True
    echo_thread = threading.Thread(target=echo_server.serve_forever, daemon=True)
    echo_thread.start()

    print("=" * 60)
    print("Level 5 Advanced Feature Validation")
    print("=" * 60)

    try:
        status1, body1, t1 = send_get_via_proxy(
            args.proxy_host,
            args.proxy_port,
            args.origin_host,
            args.origin_port,
            args.resource,
        )
        status2, body2, t2 = send_get_via_proxy(
            args.proxy_host,
            args.proxy_port,
            args.origin_host,
            args.origin_port,
            args.resource,
        )

        time.sleep(2.3)

        status3, body3, t3 = send_get_via_proxy(
            args.proxy_host,
            args.proxy_port,
            args.origin_host,
            args.origin_port,
            args.resource,
        )

        with SmartCacheOriginHandler.count_lock:
            origin_hits = SmartCacheOriginHandler.request_count

        connect_ok, connect_status = test_connect_tunnel(
            args.proxy_host,
            args.proxy_port,
            args.echo_host,
            args.echo_port,
        )

        improvement_pct = ((t1 - t2) / t1 * 100.0) if t1 > 0 else 0.0

        print(f"Request #1: {status1} | body='{body1}' | {t1:.3f}s")
        print(f"Request #2: {status2} | body='{body2}' | {t2:.3f}s")
        print(f"Request #3: {status3} | body='{body3}' | {t3:.3f}s")
        print(f"Origin hit count: {origin_hits}")
        print(f"Cache hit improvement (req1 -> req2): {improvement_pct:.1f}%")
        print(f"CONNECT status: {connect_status}")
        print()

        ok_status = (
            has_status_code(status1, 200)
            and has_status_code(status2, 200)
            and has_status_code(status3, 200)
        )
        ok_smart_cache = body1 == body2 and body3 != body2 and origin_hits == 2
        ok_performance = t2 < t1

        if ok_status and ok_smart_cache and ok_performance and connect_ok:
            print("PASS: Level 5 advanced features confirmed.")
            raise SystemExit(0)

        print("FAIL: Level 5 behavior not as expected.")
        if not ok_status:
            print("- One or more GET requests did not return HTTP 200")
        if not ok_smart_cache:
            print("- Smart cache header behavior failed (max-age handling)")
        if not ok_performance:
            print("- Cache performance gain was not observed")
        if not connect_ok:
            print("- CONNECT tunnel test failed")

        raise SystemExit(1)

    finally:
        origin_server.shutdown()
        origin_server.server_close()
        echo_server.shutdown()
        echo_server.server_close()


if __name__ == "__main__":
    main()
