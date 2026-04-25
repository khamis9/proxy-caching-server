"""
Simple password-protected admin web interface for proxy monitoring/control.
"""

import base64
import html
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from logger import Logger


class AdminInterface:
    """Admin interface server for logs, cache, and blacklist management."""

    def __init__(self, proxy_server, host: str = "127.0.0.1", port: int = 8890, password: str = "admin"):
        self.proxy_server = proxy_server
        self.host = host
        self.port = port
        self.password = password
        self._http_server = None
        self._thread = None

    def start(self) -> None:
        """Start admin web interface in a daemon thread."""
        handler_class = self._build_handler_class()
        self._http_server = ThreadingHTTPServer((self.host, self.port), handler_class)
        self._thread = threading.Thread(target=self._http_server.serve_forever, daemon=True)
        self._thread.start()
        Logger.info(f"Admin interface started on http://{self.host}:{self.port}")

    def stop(self) -> None:
        """Stop admin web interface."""
        if self._http_server is None:
            return

        self._http_server.shutdown()
        self._http_server.server_close()
        self._http_server = None
        Logger.info("Admin interface stopped")

    def _build_handler_class(self):
        admin = self

        class AdminHandler(BaseHTTPRequestHandler):
            """HTTP handler for admin endpoints."""

            def do_GET(self):
                if not self._is_authorized():
                    return

                if self.path == "/":
                    self._render_dashboard(message="")
                    return

                self.send_error(404, "Not Found")

            def do_POST(self):
                if not self._is_authorized():
                    return

                content_length = int(self.headers.get("Content-Length", "0") or "0")
                raw_body = self.rfile.read(content_length) if content_length > 0 else b""
                body = parse_qs(raw_body.decode("utf-8", errors="ignore"))
                action = self.path

                message = ""
                if action == "/clear-cache":
                    admin.proxy_server.cache.clear()
                    message = "Cache cleared."

                elif action == "/add-host":
                    value = (body.get("value", [""])[0]).strip().lower()
                    if admin.proxy_server.request_filter.add_host(value):
                        message = f"Added blocked host: {value}"
                    else:
                        message = "Host not added (empty or already exists)."

                elif action == "/remove-host":
                    value = (body.get("value", [""])[0]).strip().lower()
                    if admin.proxy_server.request_filter.remove_host(value):
                        message = f"Removed blocked host: {value}"
                    else:
                        message = "Host not removed (missing or empty)."

                elif action == "/add-keyword":
                    value = (body.get("value", [""])[0]).strip().lower()
                    if admin.proxy_server.request_filter.add_keyword(value):
                        message = f"Added blocked keyword: {value}"
                    else:
                        message = "Keyword not added (empty or already exists)."

                elif action == "/remove-keyword":
                    value = (body.get("value", [""])[0]).strip().lower()
                    if admin.proxy_server.request_filter.remove_keyword(value):
                        message = f"Removed blocked keyword: {value}"
                    else:
                        message = "Keyword not removed (missing or empty)."

                elif action == "/add-ip":
                    value = (body.get("value", [""])[0]).strip()
                    if admin.proxy_server.request_filter.add_ip(value):
                        message = f"Added blocked IP: {value}"
                    else:
                        message = "IP not added (empty or already exists)."

                elif action == "/remove-ip":
                    value = (body.get("value", [""])[0]).strip()
                    if admin.proxy_server.request_filter.remove_ip(value):
                        message = f"Removed blocked IP: {value}"
                    else:
                        message = "IP not removed (missing or empty)."

                else:
                    self.send_error(404, "Not Found")
                    return

                self._render_dashboard(message=message)

            def _is_authorized(self) -> bool:
                auth_header = self.headers.get("Authorization", "")
                if not auth_header.startswith("Basic "):
                    self._request_auth()
                    return False

                try:
                    encoded = auth_header.split(" ", 1)[1]
                    decoded = base64.b64decode(encoded).decode("utf-8", errors="ignore")
                except Exception:
                    self._request_auth()
                    return False

                if ":" not in decoded:
                    self._request_auth()
                    return False

                _, provided_password = decoded.split(":", 1)
                if provided_password != admin.password:
                    self._request_auth()
                    return False

                return True

            def _request_auth(self) -> None:
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="Proxy Admin"')
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Authentication required")

            def _render_dashboard(self, message: str) -> None:
                hits, misses, evictions, active_entries = admin.proxy_server.cache.stats()
                cache_entries = admin.proxy_server.cache.snapshot()
                filter_snapshot = admin.proxy_server.request_filter.snapshot()
                blocked_lines = self._read_log_matches("Blocked request", limit=50)
                log_tail = self._read_log_tail(limit=80)

                rows = []
                for entry in cache_entries:
                    rows.append(
                        "<tr>"
                        f"<td>{html.escape(entry['key'])}</td>"
                        f"<td>{entry['size_bytes']}</td>"
                        f"<td>{entry['age_seconds']}</td>"
                        f"<td>{entry['ttl_remaining_seconds']}</td>"
                        "</tr>"
                    )
                cache_table_rows = "".join(rows) if rows else "<tr><td colspan='4'>No entries</td></tr>"

                html_body = f"""<!doctype html>
<html>
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>Proxy Admin</title>
<style>
:root {{
  --bg: #f2f5f9;
  --surface: #ffffff;
  --text: #0f172a;
  --accent: #0ea5a4;
  --muted: #64748b;
  --danger: #dc2626;
  --border: #dbe2ea;
}}
body {{
  margin: 0;
  padding: 18px;
  background: radial-gradient(circle at top left, #dff4f4, var(--bg));
  color: var(--text);
  font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
}}
.container {{
  max-width: 1100px;
  margin: 0 auto;
}}
.card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 14px;
}}
h1 {{ margin-top: 0; }}
h2 {{ margin-top: 0; font-size: 1.1rem; }}
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
}}
.metric {{
  color: var(--muted);
  font-size: 0.93rem;
}}
.message {{
  padding: 10px;
  border-radius: 8px;
  background: #eefcfb;
  border: 1px solid #b9ece9;
  color: #0b6e6e;
  margin-bottom: 12px;
}}
form.inline {{
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}}
input[type=text] {{
  flex: 1;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px;
}}
button {{
  border: none;
  border-radius: 8px;
  padding: 8px 12px;
  background: var(--accent);
  color: white;
  cursor: pointer;
}}
button.danger {{ background: var(--danger); }}
table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 0.92rem;
}}
th, td {{
  text-align: left;
  border-bottom: 1px solid var(--border);
  padding: 8px;
  vertical-align: top;
}}
pre {{
  white-space: pre-wrap;
  margin: 0;
  max-height: 260px;
  overflow-y: auto;
  background: #0b1220;
  color: #d7e3f3;
  padding: 12px;
  border-radius: 10px;
  font-size: 0.85rem;
}}
.tag {{
  display: inline-block;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 4px 8px;
  margin: 2px;
  font-size: 0.82rem;
  color: #1e293b;
  background: #f8fbff;
}}
</style>
</head>
<body>
<div class=\"container\">
  <h1>Proxy Admin Interface</h1>
  <div class=\"metric\">Password protected panel for cache, filter rules, and logs.</div>
  {f"<div class='message'>{html.escape(message)}</div>" if message else ""}

  <div class=\"card\">
    <h2>Cache Overview</h2>
    <div class=\"metric\">hits={hits}, misses={misses}, evictions={evictions}, active_entries={active_entries}</div>
    <form method=\"post\" action=\"/clear-cache\" style=\"margin-top:10px\">
      <button class=\"danger\" type=\"submit\">Clear Cache</button>
    </form>
  </div>

  <div class=\"card\">
    <h2>Cache Contents</h2>
    <table>
      <thead>
        <tr><th>Key</th><th>Size (bytes)</th><th>Age (s)</th><th>TTL Remaining (s)</th></tr>
      </thead>
      <tbody>{cache_table_rows}</tbody>
    </table>
  </div>

  <div class=\"grid\">
    <div class=\"card\">
      <h2>Blocked Hosts</h2>
      <form class=\"inline\" method=\"post\" action=\"/add-host\"><input name=\"value\" type=\"text\" placeholder=\"example.com\" /><button type=\"submit\">Add</button></form>
      <form class=\"inline\" method=\"post\" action=\"/remove-host\"><input name=\"value\" type=\"text\" placeholder=\"example.com\" /><button class=\"danger\" type=\"submit\">Remove</button></form>
      {''.join([f"<span class='tag'>{html.escape(item)}</span>" for item in filter_snapshot['hosts']]) or "<div class='metric'>No blocked hosts</div>"}
    </div>

    <div class=\"card\">
      <h2>Blocked Keywords</h2>
      <form class=\"inline\" method=\"post\" action=\"/add-keyword\"><input name=\"value\" type=\"text\" placeholder=\"malware\" /><button type=\"submit\">Add</button></form>
      <form class=\"inline\" method=\"post\" action=\"/remove-keyword\"><input name=\"value\" type=\"text\" placeholder=\"malware\" /><button class=\"danger\" type=\"submit\">Remove</button></form>
      {''.join([f"<span class='tag'>{html.escape(item)}</span>" for item in filter_snapshot['keywords']]) or "<div class='metric'>No blocked keywords</div>"}
    </div>

    <div class=\"card\">
      <h2>Blocked IPs</h2>
      <form class=\"inline\" method=\"post\" action=\"/add-ip\"><input name=\"value\" type=\"text\" placeholder=\"203.0.113.5\" /><button type=\"submit\">Add</button></form>
      <form class=\"inline\" method=\"post\" action=\"/remove-ip\"><input name=\"value\" type=\"text\" placeholder=\"203.0.113.5\" /><button class=\"danger\" type=\"submit\">Remove</button></form>
      {''.join([f"<span class='tag'>{html.escape(item)}</span>" for item in filter_snapshot['ips']]) or "<div class='metric'>No blocked IPs</div>"}
    </div>
  </div>

  <div class=\"card\">
    <h2>Blocked Requests (from log)</h2>
    <pre>{html.escape(blocked_lines)}</pre>
  </div>

  <div class=\"card\">
    <h2>Log Tail</h2>
    <pre>{html.escape(log_tail)}</pre>
  </div>
</div>
</body>
</html>
"""

                payload = html_body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            @staticmethod
            def _read_log_tail(limit: int = 80) -> str:
                path = Logger._log_file_path
                if not path or not os.path.exists(path):
                    return "Log file not configured or not found."

                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as fp:
                        lines = fp.readlines()
                    return "".join(lines[-limit:])
                except Exception as exc:
                    return f"Failed to read log file: {exc}"

            @staticmethod
            def _read_log_matches(token: str, limit: int = 50) -> str:
                path = Logger._log_file_path
                if not path or not os.path.exists(path):
                    return "No blocked-request logs found."

                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as fp:
                        matches = [line for line in fp if token in line]
                    if not matches:
                        return "No blocked-request logs found."
                    return "".join(matches[-limit:])
                except Exception as exc:
                    return f"Failed to read blocked-request logs: {exc}"

            def log_message(self, format, *args):
                # Keep stdout focused on proxy logs.
                return

        return AdminHandler
