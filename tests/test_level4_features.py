"""
Level 4 validation script.

Validates:
1) Filtering: blocked host should return HTTP 403.
2) Persistent logging: proxy log file should contain request and block entries.
"""

import argparse
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class SimpleOriginHandler(BaseHTTPRequestHandler):
    """Simple origin server used for allowed traffic validation."""

    def do_GET(self):
        body = f"allowed-path={self.path}".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def send_raw_request(proxy_host: str, proxy_port: int, request_text: str):
    """Send one raw HTTP request through proxy and return status/body."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(10)
        sock.connect((proxy_host, proxy_port))
        sock.sendall(request_text.encode("utf-8"))

        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
    finally:
        sock.close()

    if b"\r\n\r\n" in response:
        headers, body = response.split(b"\r\n\r\n", 1)
    else:
        headers, body = response, b""

    status_line = headers.split(b"\r\n", 1)[0].decode("iso-8859-1", errors="ignore")
    body_text = body.decode("utf-8", errors="ignore")
    return status_line, body_text


def has_status_code(status_line: str, status_code: int) -> bool:
    """Return True when status line contains the expected HTTP status code."""
    parts = status_line.split()
    return len(parts) >= 2 and parts[1] == str(status_code)


def main() -> None:
    parser = argparse.ArgumentParser(description="Level 4 filtering and logging validation")
    parser.add_argument("--proxy-host", default="127.0.0.1", help="Proxy host")
    parser.add_argument("--proxy-port", type=int, default=8888, help="Proxy port")
    parser.add_argument("--origin-host", default="127.0.0.1", help="Origin host")
    parser.add_argument("--origin-port", type=int, default=18081, help="Origin port")
    parser.add_argument("--log-file", default="logs/proxy_server.log", help="Proxy log file path")
    args = parser.parse_args()

    origin_server = ThreadingHTTPServer((args.origin_host, args.origin_port), SimpleOriginHandler)
    origin_thread = threading.Thread(target=origin_server.serve_forever, daemon=True)
    origin_thread.start()

    existing_size = 0
    if os.path.exists(args.log_file):
        existing_size = os.path.getsize(args.log_file)

    print("=" * 60)
    print("Level 4 Filtering + Persistent Logging Validation")
    print("=" * 60)

    blocked_request = (
        "GET /blocked-check HTTP/1.1\r\n"
        "Host: blocked.test\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    allowed_request = (
        "GET /allowed-check HTTP/1.1\r\n"
        f"Host: {args.origin_host}:{args.origin_port}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )

    try:
        blocked_status, blocked_body = send_raw_request(args.proxy_host, args.proxy_port, blocked_request)
        allowed_status, allowed_body = send_raw_request(args.proxy_host, args.proxy_port, allowed_request)

        time.sleep(0.3)

        log_tail = ""
        if os.path.exists(args.log_file):
            with open(args.log_file, "r", encoding="utf-8", errors="ignore") as logf:
                logf.seek(existing_size)
                log_tail = logf.read()

        print(f"Blocked request status: {blocked_status}")
        print(f"Allowed request status: {allowed_status}")
        print()

        ok_block = has_status_code(blocked_status, 403)
        ok_allow = has_status_code(allowed_status, 200) and "allowed-path=/allowed-check" in allowed_body
        ok_logs = "Blocked request" in log_tail and "Requested URL" in log_tail

        if ok_block and ok_allow and ok_logs:
            print("PASS: Level 4 filtering and persistent logging confirmed.")
            raise SystemExit(0)

        print("FAIL: Level 4 behavior not as expected.")
        if not ok_block:
            print("- Blocked host did not return HTTP 403")
            print(f"  Body: {blocked_body[:200]}")
        if not ok_allow:
            print("- Allowed request did not return expected HTTP 200 response")
            print(f"  Body: {allowed_body[:200]}")
        if not ok_logs:
            print("- Expected log entries not found in persistent log tail")
        raise SystemExit(1)

    finally:
        origin_server.shutdown()
        origin_server.server_close()


if __name__ == "__main__":
    main()
