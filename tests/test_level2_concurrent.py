"""
Concurrent test client for the proxy server.

Launches multiple clients in parallel to verify that the proxy can
handle concurrent connections (Level 2 validation).
"""

import argparse
import socket
import threading
import time
from typing import Any, Dict, List
from urllib.parse import urlparse


def parse_target_url(target_url: str) -> Dict[str, Any]:
    """Parse target URL into host, port, and resource components."""
    normalized_url = target_url if "://" in target_url else f"http://{target_url}"
    parsed = urlparse(normalized_url)

    if parsed.scheme and parsed.scheme.lower() != "http":
        raise ValueError("Only HTTP URLs are supported by this test script")

    if not parsed.hostname:
        raise ValueError("Target URL must include a host")

    host = parsed.hostname
    port = parsed.port or 80
    resource = parsed.path if parsed.path else "/"
    if parsed.query:
        resource = f"{resource}?{parsed.query}"

    host_header = host if port == 80 else f"{host}:{port}"
    return {
        "host": host,
        "port": port,
        "resource": resource,
        "host_header": host_header,
    }


def run_single_client(
    client_id: int,
    target: Dict[str, Any],
    proxy_host: str,
    proxy_port: int,
    timeout: float,
    results: List[Dict[str, Any]],
) -> None:
    """Run one client request through the proxy and store the result."""
    request = (
        f"GET {target['resource']} HTTP/1.1\r\n"
        f"Host: {target['host_header']}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )

    start_time = time.perf_counter()
    sock = None

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((proxy_host, proxy_port))
        sock.sendall(request.encode("utf-8"))

        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk

        status_line = "EMPTY_RESPONSE"
        if response:
            status_line = response.split(b"\r\n", 1)[0].decode("iso-8859-1", errors="ignore")

        elapsed = time.perf_counter() - start_time
        results[client_id] = {
            "success": True,
            "status": status_line,
            "bytes": len(response),
            "elapsed": elapsed,
        }

    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        results[client_id] = {
            "success": False,
            "error": str(exc),
            "bytes": 0,
            "elapsed": elapsed,
        }

    finally:
        if sock is not None:
            sock.close()


def run_concurrent_test(
    target_url: str,
    proxy_host: str,
    proxy_port: int,
    clients: int,
    timeout: float,
) -> int:
    """Run concurrent requests and print a summary report."""
    target = parse_target_url(target_url)

    print("=" * 60)
    print("Concurrent Proxy Test")
    print("=" * 60)
    print(f"Target: http://{target['host_header']}{target['resource']}")
    print(f"Proxy: {proxy_host}:{proxy_port}")
    print(f"Clients: {clients}")
    print()

    results: List[Dict[str, Any]] = [{} for _ in range(clients)]
    threads = []

    batch_start = time.perf_counter()
    for client_id in range(clients):
        thread = threading.Thread(
            target=run_single_client,
            args=(client_id, target, proxy_host, proxy_port, timeout, results),
        )
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    total_elapsed = time.perf_counter() - batch_start

    success_count = sum(1 for result in results if result.get("success"))
    failure_count = clients - success_count

    print("Results per client:")
    for client_id, result in enumerate(results):
        if result.get("success"):
            print(
                f"  Client {client_id:02d}: OK | {result['status']} | "
                f"{result['bytes']} bytes | {result['elapsed']:.3f}s"
            )
        else:
            print(
                f"  Client {client_id:02d}: FAIL | {result.get('error', 'Unknown error')} | "
                f"{result['elapsed']:.3f}s"
            )

    print()
    print("Summary:")
    print(f"  Success: {success_count}/{clients}")
    print(f"  Failures: {failure_count}/{clients}")
    print(f"  Total elapsed: {total_elapsed:.3f}s")

    if success_count > 0:
        avg_success = sum(r["elapsed"] for r in results if r.get("success")) / success_count
        print(f"  Avg successful request time: {avg_success:.3f}s")

    return 0 if failure_count == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Concurrent proxy test script")
    parser.add_argument("--url", default="http://www.example.com/", help="Target HTTP URL")
    parser.add_argument("--proxy-host", default="127.0.0.1", help="Proxy host")
    parser.add_argument("--proxy-port", type=int, default=8888, help="Proxy port")
    parser.add_argument("--clients", type=int, default=10, help="Number of concurrent clients")
    parser.add_argument("--timeout", type=float, default=10.0, help="Socket timeout in seconds")
    args = parser.parse_args()

    exit_code = run_concurrent_test(
        target_url=args.url,
        proxy_host=args.proxy_host,
        proxy_port=args.proxy_port,
        clients=args.clients,
        timeout=args.timeout,
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
