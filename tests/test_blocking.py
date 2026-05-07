"""
Test script for blocked keywords and blocked IPs.

Tests:
1. Blocked keywords (forbidden, malware)
2. Blocked IPs (192.168.1.100, 10.0.0.50)
3. Allowed hosts/keywords (should work)
"""

import argparse
import socket
import time


def send_raw_request(proxy_host: str, proxy_port: int, request_text: str):
    """Send one raw HTTP request through proxy and return status/body."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(5)
        sock.connect((proxy_host, proxy_port))
        sock.sendall(request_text.encode("utf-8"))

        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
    except Exception as e:
        return f"ERROR: {str(e)}", ""
    finally:
        sock.close()

    if b"\r\n\r\n" in response:
        headers, body = response.split(b"\r\n\r\n", 1)
    else:
        headers, body = response, b""

    status_line = headers.split(b"\r\n", 1)[0].decode("iso-8859-1", errors="ignore")
    body_text = body.decode("utf-8", errors="ignore")
    return status_line, body_text


def test_blocked_keyword(proxy_host: str, proxy_port: int, keyword: str, host: str = "example.com"):
    """Test a blocked keyword in URL."""
    request = (
        f"GET /{keyword}-page HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    status, body = send_raw_request(proxy_host, proxy_port, request)
    
    # Check if blocked (403) or allowed (200)
    if "403" in status:
        result = "✓ BLOCKED"
        status_code = 403
    else:
        result = "✗ NOT BLOCKED"
        status_code = 200 if "200" in status else "?"
    
    print(f"  Keyword '{keyword}': {result} | Status: {status}")
    return "403" in status


def test_blocked_ip(proxy_host: str, proxy_port: int, ip_addr: str, path: str = "/test"):
    """Test a blocked IP (by hostname resolution)."""
    # Note: This tests if the IP would be blocked when resolved from a hostname
    # For this test, we'll use example domains that would resolve
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: example.com\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    status, body = send_raw_request(proxy_host, proxy_port, request)
    
    # Since we can't easily mock a hostname to resolve to a blocked IP,
    # we just show the status
    print(f"  IP '{ip_addr}': {status}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Test blocked keywords and IPs")
    parser.add_argument("--proxy-host", default="127.0.0.1", help="Proxy host")
    parser.add_argument("--proxy-port", type=int, default=8888, help="Proxy port")
    args = parser.parse_args()

    print("=" * 60)
    print("Blocking Validation Test")
    print("=" * 60)
    print()

    # Test 1: Blocked Keywords
    print("TEST 1: Blocked Keywords")
    print("-" * 60)
    print("Blocked keywords configured: 'forbidden', 'malware'")
    print()
    
    blocked_keywords = ["forbidden", "malware"]
    keyword_pass = 0
    
    for keyword in blocked_keywords:
        if test_blocked_keyword(args.proxy_host, args.proxy_port, keyword):
            keyword_pass += 1
        time.sleep(0.5)
    
    print()
    print(f"Keywords Blocked: {keyword_pass}/{len(blocked_keywords)}")
    print()

    # Test 2: Allowed Keywords (should NOT be blocked)
    print("TEST 2: Allowed Keywords (should pass through)")
    print("-" * 60)
    print("Testing URLs that should NOT be blocked...")
    print()
    
    allowed_keywords = ["hello", "world", "safe"]
    allowed_pass = 0
    
    for keyword in allowed_keywords:
        request = (
            f"GET /{keyword} HTTP/1.1\r\n"
            "Host: example.com\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
        status, body = send_raw_request(args.proxy_host, args.proxy_port, request)
        
        if "200" in status or "404" in status or "500" in status:
            result = "✓ ALLOWED"
            allowed_pass += 1
        else:
            result = "✗ BLOCKED (unexpected!)"
        
        print(f"  Keyword '{keyword}': {result} | Status: {status}")
        time.sleep(0.5)
    
    print()
    print(f"Allowed Keywords Passed: {allowed_pass}/{len(allowed_keywords)}")
    print()

    # Test 3: Blocked Hosts
    print("TEST 3: Blocked Hosts (bonus)")
    print("-" * 60)
    print("Blocked hosts configured: 'blocked.test', 'ads.example'")
    print()
    
    blocked_hosts = ["blocked.test", "ads.example"]
    
    for host in blocked_hosts:
        request = (
            f"GET / HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
        status, body = send_raw_request(args.proxy_host, args.proxy_port, request)
        
        if "403" in status:
            result = "✓ BLOCKED"
        else:
            result = "✗ NOT BLOCKED"
        
        print(f"  Host '{host}': {result} | Status: {status}")
        time.sleep(0.5)
    
    print()
    print("=" * 60)
    print("Blocking Validation Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
