import time
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from wulf_web_leader.models import AuditResult, CanonicalLead
from wulf_web_leader.audit.cache import AuditCache
from wulf_web_leader.pipeline import run_scan_pipeline
from wulf_web_leader.adapters.nominatim import NominatimClient, GeocodedLocation
from wulf_web_leader.adapters.osm import OverpassClient
from wulf_web_leader.verticals import find_vertical


def test_audit_cache_get_set(tmp_path: Path):
    cache = AuditCache(cache_dir=tmp_path, ttl_seconds=60)

    url = "https://moja-firma-test.pl"
    res = AuditResult(
        reachable=True,
        status_code=200,
        final_url=url,
        is_https=True,
        has_viewport=True,
        generator="WordPress",
    )

    # Initial state: cache miss
    assert cache.get(url) is None

    # Save to cache
    cache.set(url, res)

    # Cache hit
    cached = cache.get(url)
    assert cached is not None
    assert cached.reachable is True
    assert cached.generator == "WordPress"
    assert cached.final_url == url


def test_audit_cache_ttl_expiration(tmp_path: Path):
    # TTL = 1 second
    cache = AuditCache(cache_dir=tmp_path, ttl_seconds=1)
    url = "https://stara-strona.pl"
    res = AuditResult(reachable=False, error_message="Timeout")

    cache.set(url, res)
    # Manually backdate the timestamp to 10 seconds ago
    cache._cache[url]["timestamp"] = time.time() - 10

    # Should be expired
    assert cache.get(url) is None


@pytest.mark.asyncio
async def test_pipeline_uses_audit_cache(tmp_path: Path):
    cache = AuditCache(cache_dir=tmp_path)
    url = "https://cached-firma.pl"
    fake_audit = AuditResult(
        reachable=True,
        status_code=200,
        final_url=url,
        is_https=True,
        has_viewport=False,  # mobile unfriendly
        generator="OldJoomla",
    )
    # Pre-populate cache
    cache.set(url, fake_audit)

    vertical = find_vertical("plumbers")
    assert vertical is not None

    class MockCacheNom(NominatimClient):
        async def geocode(self, city: str, country: str):
            return GeocodedLocation(lat=50.0, lon=20.0, display_name="Test City", city="Test")

    class MockCacheOverpass(OverpassClient):
        async def execute_query(self, query: str):
            return [
                {
                    "type": "node",
                    "id": 99,
                    "lat": 50.0,
                    "lon": 20.0,
                    "tags": {
                        "name": "Firma Cached",
                        "website": url,
                        "contact:phone": "+48 17 000 00 00",
                    },
                }
            ]

    # Patch audit_website so that if it is called, it raises an AssertionError
    with patch("wulf_web_leader.pipeline.audit_website", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = AssertionError("audit_website should NOT be called on cache hit!")

        leads, _ = await run_scan_pipeline(
            country="PL",
            city="Test",
            vertical=vertical,
            do_audit=True,
            audit_cache=cache,
            no_cache=False,
            nominatim_client=MockCacheNom(),
            overpass_client=MockCacheOverpass(),
        )

        assert len(leads) == 1
        assert leads[0].name == "Firma Cached"
        assert leads[0].audit is not None
        assert leads[0].audit.generator == "OldJoomla"
        # Verify network fetcher was never called!
        mock_fetch.assert_not_called()


def test_audit_cache_dirty_flag_and_flush(tmp_path: Path):
    cache = AuditCache(cache_dir=tmp_path, ttl_seconds=60)
    assert cache._dirty is False
    assert not cache.cache_file.exists()

    url = "https://dirty-flag-test.pl"
    res = AuditResult(reachable=True, status_code=200, final_url=url)

    # Calling set() marks cache dirty but does not immediately write to disk
    cache.set(url, res)
    assert cache._dirty is True
    assert not cache.cache_file.exists()

    # In-memory access works before flush
    cached = cache.get(url)
    assert cached is not None
    assert cached.final_url == url

    # flush() writes to disk and clears _dirty
    cache.flush()
    assert cache._dirty is False
    assert cache.cache_file.exists()

    # Re-instantiating reads the persisted data from disk
    new_cache = AuditCache(cache_dir=tmp_path, ttl_seconds=60)
    assert new_cache.get(url) is not None
    assert new_cache._dirty is False

    # Calling flush() when not dirty does not re-write
    new_cache.flush()
    assert new_cache._dirty is False
