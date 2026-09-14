"""
IP-based Rate Limiter for WULF LEAD.ER web application.
Enforces a limit of 1 use per minute per IP address (for Gemini AI verifications and scans).
"""

import os
import time
from typing import Optional
from starlette.requests import Request


def get_client_ip(request: Optional[Request]) -> str:
    """Extract real client IP address considering reverse proxies and Cloudflare."""
    if not request:
        return "127.0.0.1"

    # 1. Cloudflare
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip and cf_ip.strip():
        return cf_ip.strip()

    # 2. X-Forwarded-For (take the first public client IP)
    xff = request.headers.get("x-forwarded-for")
    if xff:
        client_ip = xff.split(",")[0].strip()
        if client_ip:
            return client_ip

    # 3. X-Real-IP
    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip and x_real_ip.strip():
        return x_real_ip.strip()

    # 4. Direct socket connection
    if request.client and request.client.host:
        return request.client.host

    return "127.0.0.1"


class IPRateLimiter:
    """In-memory rate limiter tracking last access timestamps per client IP."""

    def __init__(self, cooldown_seconds: float = 60.0):
        self.cooldown_seconds = cooldown_seconds
        self._last_access: dict[str, float] = {}

    def is_disabled(self) -> bool:
        """Disabled by default to allow uninterrupted OSINT and multiple scans."""
        # Only enable if explicitly requested via ENABLE_RATE_LIMIT=1
        return os.environ.get("ENABLE_RATE_LIMIT", "0").lower() not in ("1", "true", "yes")

    def check(self, ip: str) -> tuple[bool, float]:
        """
        Check whether a request from the given IP is allowed.
        Returns:
            (is_allowed: bool, retry_after_seconds: float)
        """
        if self.is_disabled() or self.cooldown_seconds <= 0:
            return True, 0.0

        now = time.time()
        # Periodic cleanup if dictionary grows large
        if len(self._last_access) > 2000:
            self._last_access = {
                k: v for k, v in self._last_access.items()
                if now - v < self.cooldown_seconds * 2
            }

        last_time = self._last_access.get(ip, 0.0)
        elapsed = now - last_time
        if elapsed < self.cooldown_seconds:
            remaining = self.cooldown_seconds - elapsed
            return False, round(remaining, 1)

        self._last_access[ip] = now
        return True, 0.0

    def reset(self, ip: Optional[str] = None):
        """Clear rate limit records (useful for testing)."""
        if ip:
            self._last_access.pop(ip, None)
        else:
            self._last_access.clear()


# Default rate limiters: rate limiting lifted (cooldown 0s) to allow seamless OSINT
gemini_rate_limiter = IPRateLimiter(cooldown_seconds=0.0)
scan_rate_limiter = IPRateLimiter(cooldown_seconds=0.0)
