#!/usr/bin/env python3
"""Multi-threaded chat server with proper error handling"""
import http.server
import json
import http.client
import hashlib
import socketserver
import threading
import socket

PORT = 18889
HTML = "/home/pi/.openclaw/workspace/jarvis-chat.html"
JARVIS_HOST = "192.168.1.81"
JARVIS_PORT = 18789
FRIDAY_HOST = "127.0.0.1"
FRIDAY_PORT = 18789
JARVIS_TOKEN = "6c91e7579cb96dfec946988ab4c78d3fe52e232d49002e5a"
FRIDAY_TOKEN = "ea647f271570539a45aec97e12d0a329ecefe82b429fdf80"
PASSWORD = "stark-tower-2026"
PASSWORD_HASH = hashlib.sha256(PASSWORD.encode()).hexdigest()

LOGIN_PAGE = f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Jarvis Chat — Вход</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0d1117;color:#e6edf3;height:100vh;display:flex;align-items:center;justify-content:center}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:40px;width:360px;text-align:center}}
h1{{font-size:20px;margin-bottom:8px}}p{{color:#8b949e;font-size:14px;margin-bottom:24px}}
input{{width:100%;background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:10px 14px;color:#e6edf3;font-size:14px;outline:none;margin-bottom:12px}}
input:focus{{border-color:#1f6feb}}
button{{width:100%;background:#1f6feb;color:#fff;border:none;border-radius:8px;padding:10px;font-size:14px;cursor:pointer}}
button:hover{{background:#388bfd}}
.error{{color:#f85149;font-size:13px;margin-top:8px;display:none}}
</style></head>
<body>
<div class="card">
<h1>🗼 Башня Старка</h1>
<p>Введи пароль для доступа к чату</p>
<input type="password" id="pass" placeholder="Пароль" onkeydown="if(event.key==='Enter')login()">
<button onclick="login()">Войти</button>
<div class="error" id="error">Неверный пароль</div>
</div>
<script>
async function login(){{const p=document.getElementById('pass').value;const r=await fetch('/api/login',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{password:p}})}});const d=await r.json();if(d.ok){{location.reload()}}else{{document.getElementById('error').style.display='block'}}}}
</script>
</body>
</html>"""

def check_auth(request):
    # Cookie check
    cookie_header = request.headers.get("Cookie", "")
    if cookie_header:
        for c in cookie_header.split(";"):
            if c.strip().startswith("chat_auth="):
                return c.strip().split("=", 1)[1] == PASSWORD_HASH
    # Bearer token check
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and auth_header[7:] == PASSWORD:
        return True
    return False

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html") or self.path.startswith("/?"):
            if check_auth(self):
                self._serve_file(HTML)
            else:
                self._serve_text(LOGIN_PAGE, "text/html; charset=utf-8")
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/login":
            self._handle_login()
        elif self.path in ("/v1/chat/completions", "/v1/jarvis/completions"):
            if not check_auth(self):
                self._send_json(401, {"error": "auth required"})
            elif "/jarvis" in self.path:
                self._proxy_jarvis()
            else:
                self._proxy_friday()
        else:
            self.send_error(404)

    def _handle_login(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            ok = hashlib.sha256(body.get("password", "").encode()).hexdigest() == PASSWORD_HASH
            self.send_response(200 if ok else 401)
            if ok:
                self.send_header("Set-Cookie", f"chat_auth={PASSWORD_HASH}; Path=/; Max-Age=2592000; SameSite=Lax")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": ok}).encode())
        except Exception:
            self._send_json(400, {"error": "invalid request"})

    def _proxy_jarvis(self):
        self._proxy(JARVIS_HOST, JARVIS_PORT, JARVIS_TOKEN)

    def _proxy_friday(self):
        self._proxy(FRIDAY_HOST, FRIDAY_PORT, FRIDAY_TOKEN)

    def _proxy(self, host, port, token):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        conn = http.client.HTTPConnection(host, port, timeout=300)
        try:
            conn.request("POST", "/v1/chat/completions", body=body,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
            resp = conn.getresponse()

            # Check request to determine if streaming
            req_body = json.loads(body)
            is_stream = req_body.get("stream", False)

            self.send_response(resp.status)
            ct = "text/event-stream; charset=utf-8" if is_stream else "application/json; charset=utf-8"
            self.send_header("Content-Type", ct)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            # Read through HTTP response properly
            while True:
                try:
                    buf = resp.read(65536)
                    if not buf: break
                    self.wfile.write(buf)
                    self.wfile.flush()
                except socket.timeout:
                    self.wfile.write(('\ndata: {"choices":[{"delta":{"content":"\n⏱️ Таймаут. Попробуй ещё раз."}}]}\n\ndata: [DONE]\n').encode('utf-8'))
                    self.wfile.flush()
                    break
                except (BrokenPipeError, ConnectionResetError):
                    break
                except Exception as e:
                    print(f"[ERROR] Streaming error: {e}", file=sys.stderr)
                    break
        except Exception as e:
            try:
                self._send_json(502, {"error": str(e)})
            except: pass
        finally:
            conn.close()

    def _serve_file(self, path):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        with open(path, "rb") as f:
            self.wfile.write(f.read())

    def _serve_text(self, text, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache, no-store")
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))

    def _send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Cookie")
        self.end_headers()

class ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    server = ThreadedServer(("127.0.0.1", PORT), Handler)
    print(f"Chat server on port {PORT} (multi-threaded)")
    server.serve_forever()
