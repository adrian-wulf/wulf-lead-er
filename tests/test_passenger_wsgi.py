import io
import os
import sys
from pathlib import Path
import pytest

# Ensure root directory is importable
ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import passenger_wsgi


def test_passenger_wsgi_callable():
    assert hasattr(passenger_wsgi, "application"), "passenger_wsgi must export 'application'"
    assert callable(passenger_wsgi.application), "passenger_wsgi.application must be a callable WSGI entrypoint"


def test_passenger_wsgi_health_request():
    environ = {
        "REQUEST_METHOD": "GET",
        "SCRIPT_NAME": "",
        "PATH_INFO": "/health",
        "QUERY_STRING": "",
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "80",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(),
        "wsgi.errors": io.StringIO(),
        "wsgi.multithread": False,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
    }
    status_captured = []
    headers_captured = []

    def start_response(status, headers, exc_info=None):
        status_captured.append(status)
        headers_captured.append(headers)

    body_chunks = list(passenger_wsgi.application(environ, start_response))
    body = b"".join(body_chunks).decode("utf-8")

    assert len(status_captured) == 1
    assert "200 OK" in status_captured[0]
    assert '"status":"ok"' in body
    assert '"version":"0.3.0"' in body


def test_passenger_wsgi_root_dashboard_request():
    environ = {
        "REQUEST_METHOD": "GET",
        "SCRIPT_NAME": "",
        "PATH_INFO": "/",
        "QUERY_STRING": "",
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "80",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(),
        "wsgi.errors": io.StringIO(),
        "wsgi.multithread": False,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
    }
    status_captured = []
    headers_captured = []

    def start_response(status, headers, exc_info=None):
        status_captured.append(status)
        headers_captured.append(headers)

    body_chunks = list(passenger_wsgi.application(environ, start_response))
    body = b"".join(body_chunks).decode("utf-8")

    assert len(status_captured) == 1
    assert "200 OK" in status_captured[0]
    assert "WULF" in body
    assert "LEAD.ER" in body
    assert "lead-drawer" in body
    assert "--gold: #D4A418" in body
