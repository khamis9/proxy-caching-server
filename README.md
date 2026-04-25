# Proxy Caching Server

Python HTTP proxy server implemented with low-level sockets.

Implemented features:
- Level 1: Basic proxy request forwarding and relaying
- Level 2: Multithreaded concurrent client handling
- Level 3: GET response caching with TTL and max-entry policy
- Level 4: Request filtering (host/keyword/IP blacklist) and persistent file logging
- Level 5 bonus: HTTPS tunneling via CONNECT
- Level 5 bonus: Smart caching using response cache headers (Cache-Control and Expires)
- Level 5 bonus: Response-time metrics in logs (origin/cache/tunnel)
- Level 5 bonus: Password-protected admin web interface for cache/log/filter control

## Project Structure

- src/main.py: server entry point
- src/proxy_server.py: socket server and thread management
- src/client_handler.py: request handling, forwarding, caching, filtering, CONNECT tunnel
- src/http_parser.py: HTTP request and response parsing helpers
- src/cache.py: thread-safe in-memory cache (TTL + LRU-style eviction)
- src/filter.py: blacklist filtering logic
- src/logger.py: console and file logger
- src/admin_interface.py: password-protected admin dashboard and controls
- tests/test_level1_client.py: basic manual test client
- tests/test_level2_concurrent.py: Level 2 concurrency validation
- tests/test_level3_cache.py: Level 3 cache behavior validation
- tests/test_level4_features.py: Level 4 filtering + persistent logging validation
- tests/test_level5_advanced.py: Level 5 smart cache + performance + CONNECT validation

## Run Server

From project root:

python src/main.py

Default settings:
- Proxy listens on 0.0.0.0:8888
- Persistent logs stored in logs/proxy_server.log
- Admin interface listens on 127.0.0.1:8890 (Basic Auth user: admin)

Admin password:
- Set environment variable `PROXY_ADMIN_PASSWORD` before starting the server.
- If not set, default password is `admin`.

## Test Scripts

Run each script while the proxy is running:

python tests/test_level2_concurrent.py --clients 20 --url http://www.example.com/

python tests/test_level3_cache.py --proxy-host 127.0.0.1 --proxy-port 8888

python tests/test_level4_features.py --proxy-host 127.0.0.1 --proxy-port 8888 --log-file logs/proxy_server.log

python tests/test_level5_advanced.py --proxy-host 127.0.0.1 --proxy-port 8888

## Notes

- Filtering defaults are configured in src/main.py.
- Cache defaults are configured in src/main.py (ttl=60s, max_entries=100).
- All networking uses Python socket module (no requests/httpx frameworks).