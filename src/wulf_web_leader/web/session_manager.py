"""Session management and workspace isolation for Wulf Web Leader.

Provides per-session isolation via cookies and headers, allocating a dedicated
workspace directory for each client session (e.g. sessions/<session_id>/)
so that concurrent users, incognito windows, or distinct browsers do not collide.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import re
import shutil
import threading
import time
import uuid
from typing import Optional

from starlette.requests import Request

from wulf_web_leader.web.scan_manager import ScanManager

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "wulf_session_id"
SESSION_HEADER_NAME = "X-Session-ID"
COOKIE_MAX_AGE = 86400 * 30  # 30 days in seconds


def get_sessions_root_dir() -> Path:
    """Determine the base directory for storing per-session data."""
    env_dir = os.environ.get("WULF_SESSIONS_DIR") or os.environ.get("WULF_DATA_DIR")
    if env_dir:
        root = Path(env_dir).resolve()
        if "sessions" not in root.parts:
            root = root / "sessions"
    else:
        root = (Path.cwd() / "sessions").resolve()

    root.mkdir(parents=True, exist_ok=True)
    return root


def sanitize_session_id(raw_sid: Optional[str]) -> str:
    """Sanitize and validate session ID to prevent path traversal or injection.

    Returns a clean alphanumeric/hex identifier, or generates a new UUID4 hex.
    """
    if not raw_sid or not isinstance(raw_sid, str):
        return uuid.uuid4().hex

    val = raw_sid.strip()
    if "/" in val or "\\" in val or ".." in val:
        return uuid.uuid4().hex

    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", val)
    if len(cleaned) < 8 or len(cleaned) > 64:
        return uuid.uuid4().hex
    return cleaned



def get_session_id(request: Request) -> str:
    """Extract session ID safely from request state, cookies, or headers."""
    state = getattr(request, "state", None)
    state_sid = getattr(state, "session_id", None) if state else None
    if state_sid:
        return sanitize_session_id(state_sid)

    cookies = getattr(request, "cookies", None)
    if isinstance(cookies, dict):
        cookie_sid = cookies.get(SESSION_COOKIE_NAME)
        if cookie_sid:
            return sanitize_session_id(cookie_sid)

    headers = getattr(request, "headers", None)
    if hasattr(headers, "get"):
        header_sid = headers.get(SESSION_HEADER_NAME)
        if header_sid:
            return sanitize_session_id(header_sid)

    return uuid.uuid4().hex


class SessionRegistry:
    """Thread-safe registry managing per-session ScanManager instances and workspaces."""

    def __init__(self, root_dir: Optional[Path] = None) -> None:
        self.root_dir = root_dir or get_sessions_root_dir()
        self._managers: dict[str, ScanManager] = {}
        self._last_accessed: dict[str, float] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str) -> ScanManager:
        """Get or initialize a ScanManager for the specified session ID."""
        clean_sid = sanitize_session_id(session_id)
        with self._lock:
            now = time.time()
            if clean_sid in self._managers:
                self._last_accessed[clean_sid] = now
                return self._managers[clean_sid]

            session_workspace = self.root_dir / clean_sid
            session_workspace.mkdir(parents=True, exist_ok=True)

            mgr = ScanManager(workspace_dir=session_workspace)
            self._managers[clean_sid] = mgr
            self._last_accessed[clean_sid] = now
            return mgr

    def reset(self, session_id: str) -> bool:
        """Reset state and wipe files for the specified session."""
        clean_sid = sanitize_session_id(session_id)
        with self._lock:
            mgr = self._managers.get(clean_sid)
            if mgr:
                mgr.status = "idle"
                mgr.stage = "idle"
                mgr.progress = 0
                mgr.message = "Gotowy do skanowania"
                mgr.logs = []
                mgr.leads = []
                mgr.current_params = {}

            session_workspace = self.root_dir / clean_sid
            if session_workspace.is_dir():
                for child in session_workspace.iterdir():
                    try:
                        if child.is_file() or child.is_symlink():
                            child.unlink(missing_ok=True)
                        elif child.is_dir():
                            shutil.rmtree(child, ignore_errors=True)
                    except Exception as e:
                        logger.warning("Could not delete %s during session reset: %s", child, e)

            return True

    def cleanup_old_sessions(self, max_age_days: int = 7) -> int:
        """Delete session directories older than max_age_days."""
        max_age_seconds = max_age_days * 86400
        now = time.time()
        removed = 0

        with self._lock:
            if not self.root_dir.is_dir():
                return 0

            for session_dir in list(self.root_dir.iterdir()):
                if not session_dir.is_dir():
                    continue
                try:
                    stat = session_dir.stat()
                    if now - stat.st_mtime > max_age_seconds:
                        shutil.rmtree(session_dir, ignore_errors=True)
                        self._managers.pop(session_dir.name, None)
                        self._last_accessed.pop(session_dir.name, None)
                        removed += 1
                except Exception as e:
                    logger.warning("Failed to clean up old session %s: %s", session_dir, e)

        return removed


# Global singleton registry
session_registry = SessionRegistry()


async def get_manager(request: Request) -> ScanManager:
    """FastAPI dependency injecting the appropriate ScanManager for the active session."""
    sid = get_session_id(request)
    return session_registry.get(sid)
