import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse
from wulf_web_leader.models import AuditResult

DEFAULT_TTL_SECONDS = 7 * 24 * 3600  # 7 days


def normalize_cache_url(url: str) -> str:
    """Normalize URL for cache key lookups."""
    cleaned = url.strip()
    if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
        cleaned = f"https://{cleaned}"
    try:
        parsed = urlparse(cleaned)
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        return f"{parsed.scheme.lower()}://{netloc}{path}"
    except Exception:
        return cleaned.lower()


class AuditCache:
    """Persistent on-disk cache for website audit results."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
    ):
        if cache_dir is None:
            home = Path.home()
            self.cache_dir = home / ".cache" / "wulf-web-leader"
        else:
            self.cache_dir = cache_dir

        self.cache_file = self.cache_dir / "audit_cache.json"
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, dict] = {}
        self._dirty = False
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cache from disk if available."""
        try:
            if self.cache_file.is_file():
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
        except Exception:
            self._cache = {}

    def _save_cache(self) -> None:
        """Save cache to disk with secure permissions."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(self.cache_dir, 0o700)
            except Exception:
                pass

            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)

            try:
                os.chmod(self.cache_file, 0o600)
            except Exception:
                pass
        except Exception:
            pass

    def get(self, url: str | None) -> AuditResult | None:
        """Retrieve fresh cached audit result for a URL."""
        if not url:
            return None

        key = normalize_cache_url(url)
        entry = self._cache.get(key)
        if not entry:
            return None

        cached_time = entry.get("timestamp", 0.0)
        if (time.time() - cached_time) > self.ttl_seconds:
            # Expired
            return None

        result_data = entry.get("result")
        if not result_data:
            return None

        try:
            return AuditResult.model_validate(result_data)
        except Exception:
            return None

    def set(self, url: str | None, result: AuditResult) -> None:
        """Store audit result into cache and mark dirty."""
        if not url:
            return

        key = normalize_cache_url(url)
        self._cache[key] = {
            "timestamp": time.time(),
            "result": result.model_dump(mode="json"),
        }
        self._dirty = True

    def flush(self) -> None:
        """Flush cache to disk if marked dirty."""
        if self._dirty:
            self._save_cache()
            self._dirty = False

    def clear(self) -> None:
        """Clear cache in memory and on disk."""
        self._cache = {}
        self._dirty = False
        try:
            if self.cache_file.is_file():
                self.cache_file.unlink()
        except Exception:
            pass
