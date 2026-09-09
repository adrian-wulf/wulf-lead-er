import json
import os
import time
from pathlib import Path
from typing import NamedTuple
import httpx


class GeocodedLocation(NamedTuple):
    lat: float
    lon: float
    display_name: str
    city: str | None = None
    postcode: str | None = None


class NominatimClient:
    """Client for OpenStreetMap Nominatim geocoder complying with usage policies."""

    DEFAULT_USER_AGENT = "brakstrony/0.1.0 (+https://github.com/wulf-org/brakstrony)"
    DEFAULT_BASE_URL = "https://nominatim.openstreetmap.org"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        email: str | None = None,
        cache_dir: Path | None = None,
        min_interval_seconds: float = 1.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.email = email or os.getenv("BRAKSTRONY_EMAIL")
        user_agent = self.DEFAULT_USER_AGENT
        if self.email:
            user_agent = f"brakstrony/0.1.0 ({self.email}; +https://github.com/wulf-org/brakstrony)"
        self.headers = {
            "User-Agent": user_agent,
            "Accept": "application/json",
        }
        self.min_interval = min_interval_seconds
        self._last_request_time = 0.0

        if cache_dir is None:
            home = Path.home()
            self.cache_dir = home / ".cache" / "brakstrony"
        else:
            self.cache_dir = cache_dir

        self.cache_file = self.cache_dir / "geocache.json"
        self._cache: dict[str, dict] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        try:
            if self.cache_file.is_file():
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
        except Exception:
            self._cache = {}

    def _save_cache(self) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            # Ensure safe permissions
            os.chmod(self.cache_dir, 0o700)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
            os.chmod(self.cache_file, 0o600)
        except Exception:
            pass

    def _rate_limit(self) -> None:
        """Enforce strict 1 req/sec policy for Nominatim."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_time = time.time()

    async def geocode(self, city: str, country: str) -> GeocodedLocation | None:
        """Geocode city and country code into lat/lon with local caching."""
        cache_key = f"{country.upper()}:{city.strip().lower()}"
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            return GeocodedLocation(
                lat=entry["lat"],
                lon=entry["lon"],
                display_name=entry["display_name"],
                city=entry.get("city"),
                postcode=entry.get("postcode"),
            )

        self._rate_limit()

        params = {
            "city": city,
            "countrycodes": country.lower(),
            "format": "jsonv2",
            "addressdetails": "1",
            "limit": "1",
        }

        async with httpx.AsyncClient(timeout=10.0, headers=self.headers) as client:
            try:
                response = await client.get(f"{self.base_url}/search", params=params)
                response.raise_for_status()
                data = response.json()
                if not data or not isinstance(data, list):
                    return None

                first = data[0]
                lat = float(first["lat"])
                lon = float(first["lon"])
                display_name = first.get("display_name", city)
                addr = first.get("address", {})
                detected_city = addr.get("city") or addr.get("town") or addr.get("village") or city
                postcode = addr.get("postcode")

                # Update cache
                self._cache[cache_key] = {
                    "lat": lat,
                    "lon": lon,
                    "display_name": display_name,
                    "city": detected_city,
                    "postcode": postcode,
                }
                self._save_cache()

                return GeocodedLocation(
                    lat=lat,
                    lon=lon,
                    display_name=display_name,
                    city=detected_city,
                    postcode=postcode,
                )
            except Exception as e:
                # Log or return None on failure
                return None
