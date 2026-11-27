"""
Local reverse proxy: listens on plain HTTP at localhost:8080,
forwards every request to https://103.42.50.41:1031 with the campus CA cert.

Run this on your campus-connected machine alongside ngrok.
ngrok exposes localhost:8080 publicly; Streamlit Cloud calls the ngrok URL.

Usage:
    python proxy.py
"""
import http.server
import ssl
import urllib.request
import urllib.error
import os
from pathlib import Path

TARGET      = "https://103.42.50.41:1031"
LISTEN_PORT = 8080
CA_CERT     = str(Path(__file__).parent / "vm07-ca.crt")
API_KEY     = os.environ.get("TRACKB_API_KEY", "")

# Build an SSL context that trusts the campus CA
_ssl_ctx = ssl.create_default_context(cafile=CA_CERT)
_opener  = urllib.request.build_opener(
    urllib.request.HTTPSHandler(context=_ssl_ctx)
)


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[proxy] {self.address_string()} {fmt % args}")

    def _forward(self):
        # Read the incoming body
        length  = int(self.headers.get("Content-Length", 0))
        body    = self.rfile.read(length) if length else None

        # Build the upstream URL
        url = TARGET + self.path

        # Copy headers, inject the real API key if the client sent any bearer token
        fwd_headers = {}
        for key, val in self.headers.items():
            if key.lower() in ("host", "content-length", "transfer-encoding"):
                continue
            fwd_headers[key] = val
        # Always use the real key going upstream
        if API_KEY:
            fwd_headers["Authorization"] = f"Bearer {API_KEY}"

        req = urllib.request.Request(url, data=body, headers=fwd_headers,
                                     method=self.command)
        try:
            with _opener.open(req, timeout=90) as resp:
                self.send_response(resp.status)
                for key, val in resp.headers.items():
                    if key.lower() in ("transfer-encoding", "connection"):
                        continue
                    self.send_header(key, val)
                self.end_headers()
                self.wfile.write(resp.read())
        except urllib.error.HTTPError as exc:
            self.send_response(exc.code)
            self.end_headers()
            self.wfile.write(exc.read())
        except Exception as exc:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(f"Proxy error: {exc}".encode())

    do_GET  = _forward
    do_POST = _forward
    do_PUT  = _forward
    do_DELETE = _forward
    do_OPTIONS = _forward


if __name__ == "__main__":
    if not Path(CA_CERT).is_file():
        raise SystemExit(f"CA cert not found: {CA_CERT}")
    if not API_KEY:
        raise SystemExit("Set TRACKB_API_KEY before running the proxy.")
    server = http.server.HTTPServer(("127.0.0.1", LISTEN_PORT), ProxyHandler)
    print(f"Proxy listening on http://127.0.0.1:{LISTEN_PORT}")
    print(f"Forwarding to {TARGET} with CA {CA_CERT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
