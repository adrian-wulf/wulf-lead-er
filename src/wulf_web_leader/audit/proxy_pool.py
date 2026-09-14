"""
Proxy pool manager for WULF LEAD.ER.
Loads and rotates HTTP proxies (e.g. Webshare rotating proxies)
for Google Maps scraping and external OSINT candidate domain lookups.
"""

import logging
import os
from pathlib import Path
import random
import threading

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_CACHED_PROXIES: list[str] | None = None
_CACHED_FILE_PATH: Path | None = None


def _find_project_root() -> Path:
    """Find the root directory of the project."""
    curr = Path(__file__).resolve()
    for parent in curr.parents:
        if (parent / "pyproject.toml").is_file() or (parent / "src").is_dir():
            return parent
    return curr.parent.parent.parent


def get_proxies_file_path(reload: bool = False) -> Path | None:
    """Resolve the absolute path to the active proxies.txt file."""
    global _CACHED_FILE_PATH
    if not reload and _CACHED_FILE_PATH and _CACHED_FILE_PATH.is_file():
        return _CACHED_FILE_PATH

    # 1. Explicit env var
    env_path = os.getenv("PROXIES_FILE")
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if p.is_file():
            _CACHED_FILE_PATH = p
            return p

    # 2. Project data/proxies.txt
    root = _find_project_root()
    data_proxies = root / "data" / "proxies.txt"
    if data_proxies.is_file():
        _CACHED_FILE_PATH = data_proxies
        return data_proxies

    # 3. Project root proxies.txt
    root_proxies = root / "proxies.txt"
    if root_proxies.is_file():
        _CACHED_FILE_PATH = root_proxies
        return root_proxies

    # 4. User downloads fallback if available
    user_download = Path("/home/wulf/Downloads/Webshare 250 proxies(2).txt")
    if user_download.is_file():
        # Auto-convert to project data/proxies.txt if not already there
        try:
            target = root / "data" / "proxies.txt"
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(user_download, "r", encoding="utf-8") as f:
                raw_lines = [l.strip() for l in f if l.strip()]
            with open(target, "w", encoding="utf-8") as out:
                for line in raw_lines:
                    parts = line.split(":")
                    if len(parts) == 4:
                        ip, port, user, pwd = parts
                        out.write(f"http://{user}:{pwd}@{ip}:{port}\n")
            if target.is_file() and target.stat().st_size > 0:
                _CACHED_FILE_PATH = target
                return target
        except Exception as e:
            logger.debug("Failed auto-converting user download proxies: %s", e)

    return None


def get_all_proxies(reload: bool = False) -> list[str]:
    """Retrieve all loaded proxies in 'http://user:pass@host:port' format."""
    global _CACHED_PROXIES
    with _LOCK:
        if _CACHED_PROXIES is not None and not reload:
            return _CACHED_PROXIES

        path = get_proxies_file_path(reload=reload)
        if not path or not path.is_file():
            _CACHED_PROXIES = []
            return _CACHED_PROXIES

        proxies: list[str] = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if not line.startswith("http://") and not line.startswith("https://"):
                        parts = line.split(":")
                        if len(parts) == 4:
                            ip, port, user, pwd = parts
                            line = f"http://{user}:{pwd}@{ip}:{port}"
                        elif len(parts) == 2:
                            ip, port = parts
                            line = f"http://{ip}:{port}"
                    proxies.append(line)
        except Exception as e:
            logger.error("Failed loading proxies from %s: %s", path, e)

        _CACHED_PROXIES = proxies
        return _CACHED_PROXIES


def get_random_proxy() -> str | None:
    """Return a randomly chosen proxy URL from the pool, or None if empty."""
    proxies = get_all_proxies()
    if not proxies:
        return None
    return random.choice(proxies)


def has_proxies() -> bool:
    """Check if any proxies are configured and loaded."""
    return len(get_all_proxies()) > 0
