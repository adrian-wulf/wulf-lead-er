"""
WULF LEAD.ER — Phusion Passenger WSGI Entrypoint for Shared Hosting (cPanel / Plesk / CloudLinux).

FastAPI is an ASGI framework. Shared hosting environments (e.g. cPanel "Setup Python App",
Plesk Passenger, LiteSpeed WSGI) expect a synchronous WSGI callable named `application`.

We use `a2wsgi.ASGIMiddleware` to convert FastAPI's ASGI app into a standard WSGI application
with complete streaming and async event loop support.
"""

import sys
import os

# Determine project directories
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(CURRENT_DIR, "src")

# Ensure project paths are first in sys.path
for path in [SRC_DIR, CURRENT_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Automatically load .env file if present in project directory
env_file = os.path.join(CURRENT_DIR, ".env")
if os.path.isfile(env_file):
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
    except Exception:
        pass

# Optional: activate virtualenv if running in cPanel virtualenv folder
# If VIRTUAL_ENV environment variable is set or standard .venv exists
venv_path = os.environ.get("VIRTUAL_ENV") or os.path.join(CURRENT_DIR, ".venv")
site_packages_candidates = [
    os.path.join(venv_path, "lib", f"python{sys.version_info.major}.{sys.version_info.minor}", "site-packages"),
    os.path.join(venv_path, "lib64", f"python{sys.version_info.major}.{sys.version_info.minor}", "site-packages"),
]
for sp in site_packages_candidates:
    if os.path.exists(sp) and sp not in sys.path:
        sys.path.insert(0, sp)

# Convert ASGI -> WSGI callable
import threading

_middleware = None
_pid = None
_lock = threading.Lock()

try:
    from a2wsgi import ASGIMiddleware
    from wulf_web_leader.web.app import app as fastapi_app

    def get_middleware():
        global _middleware, _pid
        current_pid = os.getpid()
        if _middleware is None or _pid != current_pid:
            with _lock:
                if _middleware is None or _pid != current_pid:
                    _pid = current_pid
                    _middleware = ASGIMiddleware(fastapi_app)
        return _middleware

    def application(environ, start_response):
        return get_middleware()(environ, start_response)

except Exception as exc:
    # Fail-safe error page for shared hosting debugging
    def application(environ, start_response):
        status = "500 Internal Server Error"
        response_headers = [("Content-type", "text/html; charset=utf-8")]
        start_response(status, response_headers)
        error_html = f"""
        <html>
        <head><title>WULF LEAD.ER — Passenger Initialization Error</title></head>
        <body style="background:#080808; color:#F5F5F5; font-family:monospace; padding:30px;">
            <h2 style="color:#D4A418;">WULF LEAD.ER — Passenger WSGI Error</h2>
            <p>Nie udało się załadować aplikacji FastAPI przez WSGI.</p>
            <pre style="background:#181818; padding:15px; border:1px solid #303030; color:#ef4444;">{exc}</pre>
            <p style="color:#8A8F96;">Upewnij się, że zainstalowano zależności: <code>pip install -e . a2wsgi</code></p>
        </body>
        </html>
        """
        return [error_html.encode("utf-8")]
