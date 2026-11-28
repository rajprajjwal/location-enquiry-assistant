"""
Local reverse proxy: listens on plain HTTP at localhost:8080 and forwards to the institute endpoints.

  /v1/embeddings  -> https://103.42.50.41:1035  (vm02-ca.crt, EMBED_API_KEY)
  everything else -> https://103.42.50.41:1031  (vm07-ca.crt, TRACKB_API_KEY)

Run this on your campus-connected machine alongside ngrok.
ngrok exposes localhost:8080 publicly; Streamlit Cloud calls the ngrok URL for chat and embeddings.

Usage:
    TRACKB_API_KEY=... EMBED_API_KEY=... python proxy.py
"""
import http.server
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path

LISTEN_PORT = 8080
HERE = Path(__file__).parent


def _route(target, ca_file, key_variable):
    ca_cert = HERE / ca_file
    if not ca_cert.is_file():
        raise SystemExit(f"CA cert not found: {ca_cert}")
    key = os.environ.get(key_variable, "")
    if not key:
        raise SystemExit(f"Set {key_variable} before running the proxy.")
    context = ssl.create_default_context(cafile=str(ca_cert))
    return {"target": target, "ca": ca_cert.name, "key": key,
            "opener": urllib.request.build_opener(urllib.request.HTTPSHandler(context=context))}


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    chat = None
    embeddings = None

    def log_message(self, fmt, *args):
        print(f"[proxy] {self.address_string()} {fmt % args}")

    def _forward(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else None
        route = self.embeddings if self.path.split("?")[0].endswith("/embeddings") else self.chat

        headers = {key: value for key, value in self.headers.items()
                   if key.lower() not in ("host", "content-length", "transfer-encoding")}
        # The upstream key always comes from this machine, not from the caller.
        headers["Authorization"] = f"Bearer {route['key']}"

        request = urllib.request.Request(route["target"] + self.path, data=body, headers=headers, method=self.command)
        try:
            with route["opener"].open(request, timeout=90) as response:
                self.send_response(response.status)
                for key, value in response.headers.items():
                    if key.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(key, value)
                self.end_headers()
                self.wfile.write(response.read())
        except urllib.error.HTTPError as exc:
            self.send_response(exc.code)
            self.end_headers()
            self.wfile.write(exc.read())
        except Exception as exc:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(f"Proxy error: {type(exc).__name__}".encode())

    do_GET = _forward
    do_POST = _forward
    do_PUT = _forward
    do_DELETE = _forward
    do_OPTIONS = _forward


if __name__ == "__main__":
    ProxyHandler.chat = _route("https://103.42.50.41:1031", "vm07-ca.crt", "TRACKB_API_KEY")
    ProxyHandler.embeddings = _route("https://103.42.50.41:1035", "vm02-ca.crt", "EMBED_API_KEY")
    # Threaded, so an embedding request does not wait behind a slow chat completion.
    server = http.server.ThreadingHTTPServer(("127.0.0.1", LISTEN_PORT), ProxyHandler)
    print(f"Proxy listening on http://127.0.0.1:{LISTEN_PORT}")
    for name, route in (("chat", ProxyHandler.chat), ("embeddings", ProxyHandler.embeddings)):
        print(f"  {name:<10} -> {route['target']} (CA {route['ca']})")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
